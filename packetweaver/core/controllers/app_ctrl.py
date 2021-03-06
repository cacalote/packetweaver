# coding: utf8
import sys
import argparse
import threading
import os
import select
import signal
import time
import packetweaver.core.controllers.cmd_line_ctrl as cmd_line_ctrl
import packetweaver.core.controllers.ctrl as ctrl
import packetweaver.core.controllers.shell_ctrl as shell_ctrl
import packetweaver.core.models.app_model as app_model
import packetweaver.core.models.abilities.threaded_ability_base as threaded_ability
import packetweaver.core.models.modules.module_factory as module_factory
import packetweaver.core.views.view_interface as view_interface
import packetweaver.core.views.text as output


class AppCtrl(ctrl.Ctrl):
    def __init__(self, conf_file_path, cli_args, rem_args, view=output.Log()):
        """ Main controller of the framework

        Will instantiate the correct user interface depending of its parameters

        :param conf_file_path: path (relative to pw.py or absolute) to the pw.ini file
        :param cli_args: argparse successfully parsed arguments
        :param rem_args: argparse remaining arguments
        :param view: a View object, by default Log()
        """
        super(AppCtrl, self).__init__()

        self._view = view
        self._cli_args = cli_args
        self._rem_args = rem_args

        self._app_model = app_model.AppModel(conf_file_path)
        self._module_factory = module_factory.ModuleFactory(self._app_model, self._view)

        self._ctrl = None

        self.nb_max_pkg = 20  # safe guard

    def pre_process(self):
        """ Initialize the app

        Add in pythonpath user specific dependencies (for source based python libraries)
        Instantiate the correct controller using the first command line argument
        """
        # Load custom dependencies
        sys.path += self._app_model.get_dependencies()

        # choose ctrl
        if self._cli_args.subcmd == 'interactive':
            self._ctrl = shell_ctrl.ShellCtrl(self._app_model, self._module_factory, view=self._view)
        else:
            self._ctrl = cmd_line_ctrl.CmdLineCtrl(
                self._cli_args, self._rem_args,
                self._app_model, self._module_factory, self._view
            )

    def process(self):
        """ Run the selected controller """
        self._ctrl.execute()

    def post_process(self):
        for i in range(12):
            l = threading.enumerate()
            # Is the main thread the only thread remaining?
            if len(l) == 1:
                # Great! Let's just quit, then.
                return

            self._view.warning('Trying to stop the remaining threads. {} to go.'.format(len(l) - 1))
            for t in l:
                if isinstance(t, threaded_ability.ThreadedAbilityBase):
                    t.stop()

            # Let's give them some time to stop
            time.sleep(1)
            for t in l[:]:
                # Join every dead threads
                if not t.is_alive():
                    self._view.warning('Bang!')
                    t.join(0.1)
                    l.pop(l.index(t))

            if len(l) == 1:
                # Great! Let's just quit, then.
                self._view.warning('All clean. Have a nice day :)')
                return

            self._view.warning('Still some loose ends to tie (i.e. unterminated threads). Suicide? (y/N)')
            rlist, _, _ = select.select([sys.stdin], [], [], 5)
            if len(rlist) > 0:
                s = rlist[0].readline().strip()
                if s.lower() == 'y':
                    self._view.error('Bang!')
                    os.kill(os.getpid(), signal.SIGTERM)
                    # Never returns
                    return
        self._view.error('Timeout. Bang!')
        os.kill(os.getpid(), signal.SIGTERM)


