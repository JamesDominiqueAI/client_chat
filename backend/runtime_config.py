from __future__ import annotations

import os
from functools import lru_cache


@lru_cache(maxsize=16)
def _read_ssm_parameter(name: str) -> str:
    import boto3

    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    kwargs = {"region_name": region} if region else {}
    client = boto3.client("ssm", **kwargs)
    response = client.get_parameter(Name=name, WithDecryption=True)
    return response["Parameter"]["Value"]


def config_value(value_env: str, parameter_env: str, default: str = "") -> str:
    direct = os.getenv(value_env, "").strip()
    if direct:
        return direct
    parameter_name = os.getenv(parameter_env, "").strip()
    if parameter_name:
        return _read_ssm_parameter(parameter_name)
    return default
