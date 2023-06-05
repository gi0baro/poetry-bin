from __future__ import annotations

import os

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from cleo.io.buffered_io import BufferedIO
from cleo.io.null_io import NullIO
from packaging.utils import canonicalize_name

from poetry.factory import Factory
from poetry.publishing.publisher import Publisher


if TYPE_CHECKING:
    from pytest_mock import MockerFixture

    from tests.conftest import Config
    from tests.types import FixtureDirGetter


def test_publish_publishes_to_pypi_by_default(
    fixture_dir: FixtureDirGetter, mocker: MockerFixture, config: Config
) -> None:
    uploader_auth = mocker.patch("poetry.publishing.uploader.Uploader.auth")
    uploader_upload = mocker.patch("poetry.publishing.uploader.Uploader.upload")
    poetry = Factory().create_poetry(fixture_dir("sample_project"))
    poetry._config = config
    poetry.config.merge(
        {"http-basic": {"pypi": {"username": "foo", "password": "bar"}}}
    )
    publisher = Publisher(poetry, NullIO())

    publisher.publish(None, None, None)

    assert [("foo", "bar")] == uploader_auth.call_args
    assert [
        ("https://upload.pypi.org/legacy/",),
        {"cert": True, "client_cert": None, "dry_run": False, "skip_existing": False},
    ] == uploader_upload.call_args


@pytest.mark.parametrize("fixture_name", ["sample_project", "with_default_source"])
def test_publish_can_publish_to_given_repository(
    fixture_dir: FixtureDirGetter,
    mocker: MockerFixture,
    config: Config,
    fixture_name: str,
) -> None:
    uploader_auth = mocker.patch("poetry.publishing.uploader.Uploader.auth")
    uploader_upload = mocker.patch("poetry.publishing.uploader.Uploader.upload")

    config.merge(
        {
            "repositories": {"foo": {"url": "http://foo.bar"}},
            "http-basic": {"foo": {"username": "foo", "password": "bar"}},
        }
    )

    mocker.patch("poetry.config.config.Config.create", return_value=config)
    poetry = Factory().create_poetry(fixture_dir(fixture_name))

    io = BufferedIO()
    publisher = Publisher(poetry, io)

    publisher.publish("foo", None, None)

    assert [("foo", "bar")] == uploader_auth.call_args
    assert [
        ("http://foo.bar",),
        {"cert": True, "client_cert": None, "dry_run": False, "skip_existing": False},
    ] == uploader_upload.call_args
    project_name = canonicalize_name(fixture_name)
    assert f"Publishing {project_name} (1.2.3) to foo" in io.fetch_output()


def test_publish_raises_error_for_undefined_repository(
    fixture_dir: FixtureDirGetter, config: Config
) -> None:
    poetry = Factory().create_poetry(fixture_dir("sample_project"))
    poetry._config = config
    poetry.config.merge(
        {"http-basic": {"my-repo": {"username": "foo", "password": "bar"}}}
    )
    publisher = Publisher(poetry, NullIO())

    with pytest.raises(RuntimeError):
        publisher.publish("my-repo", None, None)


def test_publish_uses_token_if_it_exists(
    fixture_dir: FixtureDirGetter, mocker: MockerFixture, config: Config
) -> None:
    uploader_auth = mocker.patch("poetry.publishing.uploader.Uploader.auth")
    uploader_upload = mocker.patch("poetry.publishing.uploader.Uploader.upload")
    poetry = Factory().create_poetry(fixture_dir("sample_project"))
    poetry._config = config
    poetry.config.merge({"pypi-token": {"pypi": "my-token"}})
    publisher = Publisher(poetry, NullIO())

    publisher.publish(None, None, None)

    assert [("__token__", "my-token")] == uploader_auth.call_args
    assert [
        ("https://upload.pypi.org/legacy/",),
        {"cert": True, "client_cert": None, "dry_run": False, "skip_existing": False},
    ] == uploader_upload.call_args


def test_publish_uses_cert(
    fixture_dir: FixtureDirGetter, mocker: MockerFixture, config: Config
) -> None:
    cert = "path/to/ca.pem"
    uploader_auth = mocker.patch("poetry.publishing.uploader.Uploader.auth")
    uploader_upload = mocker.patch("poetry.publishing.uploader.Uploader.upload")
    poetry = Factory().create_poetry(fixture_dir("sample_project"))
    poetry._config = config
    poetry.config.merge(
        {
            "repositories": {"foo": {"url": "https://foo.bar"}},
            "http-basic": {"foo": {"username": "foo", "password": "bar"}},
            "certificates": {"foo": {"cert": cert}},
        }
    )
    publisher = Publisher(poetry, NullIO())

    publisher.publish("foo", None, None)

    assert [("foo", "bar")] == uploader_auth.call_args
    assert [
        ("https://foo.bar",),
        {
            "cert": Path(cert),
            "client_cert": None,
            "dry_run": False,
            "skip_existing": False,
        },
    ] == uploader_upload.call_args


def test_publish_uses_client_cert(
    fixture_dir: FixtureDirGetter, mocker: MockerFixture, config: Config
) -> None:
    client_cert = "path/to/client.pem"
    uploader_upload = mocker.patch("poetry.publishing.uploader.Uploader.upload")
    poetry = Factory().create_poetry(fixture_dir("sample_project"))
    poetry._config = config
    poetry.config.merge(
        {
            "repositories": {"foo": {"url": "https://foo.bar"}},
            "certificates": {"foo": {"client-cert": client_cert}},
        }
    )
    publisher = Publisher(poetry, NullIO())

    publisher.publish("foo", None, None)

    assert [
        ("https://foo.bar",),
        {
            "cert": True,
            "client_cert": Path(client_cert),
            "dry_run": False,
            "skip_existing": False,
        },
    ] == uploader_upload.call_args


def test_publish_read_from_environment_variable(
    fixture_dir: FixtureDirGetter,
    environ: None,
    mocker: MockerFixture,
    config: Config,
) -> None:
    os.environ["POETRY_REPOSITORIES_FOO_URL"] = "https://foo.bar"
    os.environ["POETRY_HTTP_BASIC_FOO_USERNAME"] = "bar"
    os.environ["POETRY_HTTP_BASIC_FOO_PASSWORD"] = "baz"
    uploader_auth = mocker.patch("poetry.publishing.uploader.Uploader.auth")
    uploader_upload = mocker.patch("poetry.publishing.uploader.Uploader.upload")
    poetry = Factory().create_poetry(fixture_dir("sample_project"))
    publisher = Publisher(poetry, NullIO())

    publisher.publish("foo", None, None)

    assert [("bar", "baz")] == uploader_auth.call_args
    assert [
        ("https://foo.bar",),
        {"cert": True, "client_cert": None, "dry_run": False, "skip_existing": False},
    ] == uploader_upload.call_args
