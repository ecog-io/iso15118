import asyncio
import logging
from typing import Coroutine, List, Optional

from iso15118.shared.exceptions import (
    NoSupportedAuthenticationModes,
    NoSupportedEnergyServices,
    NoSupportedProtocols,
)
from iso15118.shared.messages.enums import AuthEnum, Protocol, ServiceV20

logger = logging.getLogger(__name__)


def _format_list(read_settings: List[str]) -> List[str]:
    read_settings = list(filter(None, read_settings))
    read_settings = [setting.strip().upper() for setting in read_settings]
    read_settings = list(set(read_settings))
    return read_settings


def load_requested_protocols(read_protocols: Optional[List[str]]) -> List[Protocol]:
    supported_protocols = [
        "ISO_15118_2",
        "ISO_15118_20_AC",
        "ISO_15118_20_DC",
        "DIN_SPEC_70121",
    ]

    protocols = _format_list(read_protocols)
    valid_protocols = list(set(protocols).intersection(supported_protocols))
    if not valid_protocols:
        raise NoSupportedProtocols(
            f"No supported protocols configured. Supported protocols are "
            f"{supported_protocols} and could be configured in evcc_config.json"
        )
    return [Protocol[name] for name in valid_protocols if name in Protocol.__members__]


def load_requested_energy_services(
    read_services: Optional[List[str]],
) -> List[ServiceV20]:
    supported_services = [
        "AC",
        "DC",
        "WPT",
        "DC_ACDP",
        "AC_BPT",
        "DC_BPT",
        "DC_ACDP_BPT",
        "INTERNET",
        "PARKING_STATUS",
        "MCS",
        "MCS_BPT",
    ]

    services = _format_list(read_services)
    valid_services = list(set(services).intersection(supported_services))
    if not valid_services:
        raise NoSupportedEnergyServices(
            f"No supported energy services configured. Supported energy services are "
            f"{supported_services} and could be configured in evcc_config.json"
        )
    return [
        ServiceV20[name] for name in valid_services if name in ServiceV20.__members__
    ]


def load_requested_auth_modes(read_auth_modes: Optional[List[str]]) -> List[AuthEnum]:
    default_auth_modes = [
        "EIM",
        "PNC",
    ]
    auth_modes = _format_list(read_auth_modes)
    valid_auth_options = list(set(auth_modes).intersection(default_auth_modes))
    if not valid_auth_options:
        raise NoSupportedAuthenticationModes(
            f"No supported authentication modes configured. Supported auth modes"
            f" are {default_auth_modes} and could be configured in .env"
            f" file with key 'AUTH_MODES'"
        )
    return [AuthEnum[x] for x in valid_auth_options]


async def cancel_task(task):
    """Cancel the task safely"""
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def wait_for_tasks(
    await_tasks: List[Coroutine], return_when=asyncio.FIRST_EXCEPTION
):
    """
    Method to run multiple tasks concurrently.
    return_when is used directly in the asyncio.wait call and sets the
    condition to cancel all running tasks and return.
    The arguments for it can be:
    asyncio.FIRST_COMPLETED, asyncio.FIRST_EXCEPTION or
    asyncio.ALL_COMPLETED
    check:
    https://docs.python.org/3/library/asyncio-task.html#waiting-primitives)

    Similar solutions for awaiting for several tasks can be found in:
    * https://python.plainenglish.io/how-to-manage-exceptions-when-waiting-on-multiple-asyncio-tasks-a5530ac10f02  # noqa: E501
    * https://stackoverflow.com/questions/63583822/asyncio-wait-on-multiple-tasks-with-timeout-and-cancellation  # noqa: E501

    """
    tasks = []

    for task in await_tasks:
        if not isinstance(task, asyncio.Task):
            new_task = asyncio.create_task(task)
            tasks.append(new_task)
        else:
            tasks.append(task)

    done, pending = await asyncio.wait(tasks, return_when=return_when)

    for pending_task in pending:
        await cancel_task(pending_task)

    for done_task in done:
        try:
            done_task.result()
        except Exception as e:
            logger.exception(e)
