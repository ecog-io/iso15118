import logging
import os
from dataclasses import dataclass
from typing import Optional

import environs

from iso15118.shared.network import validate_nic
from iso15118.shared.settings import load_shared_settings, shared_settings

logger = logging.getLogger(__name__)


@dataclass
class Config:
    iface: Optional[str] = None
    log_level: Optional[str] = None
    ev_config_file_path: str = None

    def load_envs(self, env_path: Optional[str] = None) -> None:
        """
        Tries to load the .env file containing all the project settings.
        If `env_path` is not specified, it will get the .env on the current
        working directory of the project

        Args:
            env_path (str): Absolute path to the location of the .env file
        """
        env = environs.Env(eager=False)
        if not env_path:
            env_path = os.getcwd() + "/.env"
        env.read_env(path=env_path)  # read .env file, if it exists

        self.iface = env.str("NETWORK_INTERFACE", default="eth0")
        # validate the NIC selected
        validate_nic(self.iface)

        self.log_level = env.str("LOG_LEVEL", default="INFO")

        self.ev_config_file_path = str(
            env.path(
                "EVCC_CONFIG_PATH",
                default="iso15118/shared/examples/evcc/iso15118_2/evcc_config_eim_ac.json",  # noqa
            )
        )
        env.seal()  # raise all errors at once, if any
        load_shared_settings()
        logger.info("EVCC environment settings:")
        for key, value in shared_settings.items():
            logger.info(f"{key:30}: {value}")
        for key, value in env.dump().items():
            logger.info(f"{key:30}: {value}")


RESUME_SELECTED_AUTH_OPTION = None
RESUME_SESSION_ID = None
RESUME_REQUESTED_ENERGY_MODE = None
