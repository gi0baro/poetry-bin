.PHONY: _path_build _path_lib _path_assets _build_posix _build_win assets pack patches sign tests

ARCH_LINUX := x86_64-unknown-linux-gnu
ARCH_MAC_INTEL := x86_64-apple-darwin
ARCH_MAC_ARM := aarch64-apple-darwin
ARCH_WIN := x86_64-pc-windows-msvc
TARGET := install
BUILD_VERSION := latest

_path_build:
	$(eval BUILDPATH := build/${ARCH}/release/${TARGET})
_path_bin:
	$(eval BINPATH := ${BUILDPATH}${BIN_SUFFIX})
_path_lib: _path_build
	$(eval LIBPATH := ${BUILDPATH}/lib)
_path_assets: _path_build
	$(eval ASSETSPATH := ${BUILDPATH}/assets)

clean_build: _path_build
	@rm -rf ${BUILDPATH}

clean_dist:
	@rm -rf dist

clean_vendor:
	@rm -rf vendor

patches:
	@cd src/importlib_metadata && git diff --binary HEAD > ../../patches/importlib_metadata.patch
	@cd src/poetry-core && git diff --binary HEAD > ../../patches/poetry-core.patch
	@cd src/poetry && git diff --binary HEAD > ../../patches/poetry.patch
	@cd src/requests && git diff --binary HEAD > ../../patches/requests.patch
	@cd src/virtualenv && git diff --binary HEAD > ../../patches/virtualenv.patch

apply_patches:
	@cd src/importlib_metadata && git apply --reject --ignore-whitespace ../../patches/importlib_metadata.patch
	@cd src/poetry-core && git apply --reject --ignore-whitespace ../../patches/poetry-core.patch
	@cd src/poetry && git apply --reject --ignore-whitespace ../../patches/poetry.patch
	@cd src/requests && git apply --reject --ignore-whitespace ../../patches/requests.patch
	@cd src/virtualenv && git apply --reject --ignore-whitespace ../../patches/virtualenv.patch

vendor: clean_vendor
	@mkdir -p vendor
	@cp -R src/* vendor
	@find vendor -type d -name .git | xargs rm -r

tests:
	@cd vendor/importlib_metadata && \
		python -m venv .venv && \
		.venv/bin/pip install .[testing] pyfakefs && \
		.venv/bin/python -m unittest discover && \
		rm -r .venv
	@cd vendor/requests && \
		python -m venv .venv && \
		.venv/bin/pip install -e .[socks] && \
		.venv/bin/pip install -r requirements-dev.txt && \
		.venv/bin/pytest tests && \
		rm -r .venv
	@cd vendor/virtualenv && \
		python -m venv .venv && \
		.venv/bin/pip install .[testing] && \
		.venv/bin/pytest && \
		rm -r .venv
	@cd vendor/poetry-core && \
		python -m venv .venv && \
		.venv/bin/pip install -r vendors/deps.txt && \
		.venv/bin/pip install ../jsonschema ../requests ../virtualenv . && \
		.venv/bin/pip install build pytest pytest-mock && \
		.venv/bin/pytest && \
		rm -r .venv
	@cd vendor/poetry && \
		python -m venv .venv && \
		.venv/bin/pip install ../importlib_metadata ../jsonschema ../requests ../virtualenv && \
		.venv/bin/pip install -r ../poetry-core/vendors/deps.txt && \
		.venv/bin/pip install ../poetry-core . && \
		.venv/bin/pip install httpretty pytest pytest-mock && \
		.venv/bin/pytest && \
		rm -r .venv

build_linux: ARCH := ${ARCH_LINUX}
build_linux: _build_posix assets

build_mac: ARCH := ${ARCH_MAC_INTEL}
build_mac: _build_posix assets sign

build_win: ARCH := ${ARCH_WIN}
build_win: _build_win assets

_build_posix: _path_build _path_lib clean_build
	pyoxidizer build --release --target-triple=${ARCH}
	@mv ${BUILDPATH}/bin/lib ${BUILDPATH}
	@cp -a vendor/poetry-core/poetry/core/_vendor/. ${LIBPATH}

_build_win: _path_build _path_lib clean_build
	pyoxidizer build --release --target-triple=${ARCH} --var WIN_BUILD 1
	@cp -a vendor/poetry-core/poetry/core/_vendor/. ${LIBPATH}

assets: _path_assets
	@mkdir -p ${ASSETSPATH}
	@mkdir -p ${ASSETSPATH}/core/version
	@mkdir -p ${ASSETSPATH}/virtualenv/create
	@mkdir -p ${ASSETSPATH}/virtualenv/discovery
	@mkdir -p ${ASSETSPATH}/virtualenv/seed/wheels
	@cp -R vendor/poetry-core/src/poetry/core/version/grammars ${ASSETSPATH}/core/version/grammars
	@cp vendor/virtualenv/src/virtualenv/create/debug.py ${ASSETSPATH}/virtualenv/create/debug.py
	@cp vendor/virtualenv/src/virtualenv/discovery/py_info.py ${ASSETSPATH}/virtualenv/discovery/py_info.py
	@cp vendor/virtualenv/src/virtualenv/seed/wheels/embed/*.whl ${ASSETSPATH}/virtualenv/seed/wheels

sign: _path_build _path_lib
	@codesign -s - ${BUILDPATH}/bin/poetry
	@find ${LIBPATH} -name '*.so' -type f | xargs -I $$ codesign -s - $$

verify_build_linux: ARCH := ${ARCH_LINUX}
verify_build_linux: BIN_SUFFIX := /bin
verify_build_linux: _verify_build

verify_build_mac: ARCH := ${ARCH_MAC_INTEL}
verify_build_mac: BIN_SUFFIX := /bin
verify_build_mac: _verify_build

verify_build_win: ARCH := ${ARCH_WIN}
verify_build_win: _verify_build

_verify_build: _path_build _path_bin
	${BINPATH}/poetry --version
	${BINPATH}/poetry config virtualenvs.in-project true
	@cd tests && ../${BINPATH}/poetry install
	@rm -rf tests/.venv

pack_linux: ARCH := ${ARCH_LINUX}
pack_linux: pack

pack_mac: ARCH := ${ARCH_MAC_INTEL}
pack_mac: pack

pack_win: ARCH := ${ARCH_WIN}
pack_win: pack

pack: _path_build clean_dist
	@mkdir -p dist
	@cd ${BUILDPATH} && tar -czvf poetry-bin-${BUILD_VERSION}-${ARCH}.tar.gz *
	@mv ${BUILDPATH}/poetry-bin-${BUILD_VERSION}-${ARCH}.tar.gz dist
	@openssl sha256 < dist/poetry-bin-${BUILD_VERSION}-${ARCH}.tar.gz | sed 's/^.* //' > dist/poetry-bin-${BUILD_VERSION}-${ARCH}.sha256sum
	@cat dist/poetry-bin-${BUILD_VERSION}-${ARCH}.sha256sum
