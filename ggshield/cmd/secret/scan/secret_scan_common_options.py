from typing import Callable, List, Optional

import click

from ggshield.cmd.common_options import (
    AnyFunction,
    add_common_options,
    create_config_callback,
    get_config_from_context,
)
from ggshield.core.config.user_config import SecretConfig
from ggshield.core.filter import init_exclusion_regexes
from ggshield.core.utils import IGNORED_DEFAULT_WILDCARDS


def _get_secret_config(ctx: click.Context) -> SecretConfig:
    return get_config_from_context(ctx).secret


_exit_zero_option = click.option(
    "--exit-zero",
    is_flag=True,
    default=None,
    envvar="GITGUARDIAN_EXIT_ZERO",
    help="Always return a 0 (non-error) status code, even if incidents are found."
    "The env var GITGUARDIAN_EXIT_ZERO can also be used to set this option.",
    callback=create_config_callback("exit_zero"),
)


def _exclude_callback(
    ctx: click.Context, param: click.Parameter, value: Optional[List[str]]
) -> Optional[List[str]]:
    ignored_paths = _get_secret_config(ctx).ignored_paths
    if value is not None:
        ignored_paths.update(value)

    ignored_paths.update(IGNORED_DEFAULT_WILDCARDS)
    ctx.obj["exclusion_regexes"] = init_exclusion_regexes(ignored_paths)
    return value


_exclude_option = click.option(
    "--exclude",
    default=None,
    type=click.Path(),
    help="Do not scan the specified path.",
    multiple=True,
    callback=_exclude_callback,
)


_ignore_known_secrets_option = click.option(
    "--ignore-known-secrets",
    is_flag=True,
    default=None,
    help="Ignore secrets already known by GitGuardian dashboard",
    callback=create_config_callback("ignore_known_secrets"),
)


def add_secret_scan_common_options() -> Callable[[AnyFunction], AnyFunction]:
    def decorator(cmd: AnyFunction) -> AnyFunction:
        add_common_options()(cmd)
        _exit_zero_option(cmd)
        _exclude_option(cmd)
        _ignore_known_secrets_option(cmd)
        return cmd

    return decorator