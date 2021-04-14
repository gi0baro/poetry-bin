.PHONY: _path_build _path_lib _path_assets _build_posix _build_win assets pack patches sign

ARCH_LINUX := x86_64-unknown-linux-gnu
ARCH_MAC := x86_64-apple-darwin
ARCH_WIN := x86_64-pc-windows-msvc
BUILD_VERSION := latest

_path_build:
	$(eval BUILDPATH := build/${ARCH}/release/${TARGET})
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
	@cd src/certifi && git diff --binary HEAD > ../../patches/certifi.patch
	@cd src/importlib_metadata && git diff --binary HEAD > ../../patches/importlib_metadata.patch
	@cd src/poetry-core && git diff --binary HEAD > ../../patches/poetry-core.patch
	@cd src/poetry && git diff --binary HEAD > ../../patches/poetry.patch
	@cd src/virtualenv && git diff --binary HEAD > ../../patches/virtualenv.patch

vendor: clean_vendor
	@mkdir -p vendor
	@cp -R src/* vendor
	@find vendor -type d -name .git | xargs rm -r

build_linux: ARCH := ${ARCH_LINUX}
build_linux: TARGET := posix
build_linux: _build_posix assets

build_mac: ARCH := ${ARCH_MAC}
build_mac: TARGET := posix
build_mac: _build_posix assets sign

build_win: ARCH := ${ARCH_WIN}
build_win: TARGET := win
build_win: _build_win assets

_build_posix: _path_build _path_lib clean_build
	pyoxidizer build --release --target-triple=${ARCH}
	@mv ${BUILDPATH}/bin/lib ${BUILDPATH}
	@cp -R vendor/poetry-core/poetry/core/_vendor/* ${LIBPATH}

_build_win: _path_build clean_build
	pyoxidizer build --release --target-triple=${ARCH} win
	@cp -R vendor/poetry-core/poetry/core/_vendor/* ${BUILDPATH}/bin/lib

assets: _path_assets
	@mkdir -p ${ASSETSPATH}
	@mkdir -p ${ASSETSPATH}/virtualenv
	@mkdir -p ${ASSETSPATH}/virtualenv/activation
	@cp vendor/certifi/certifi/cacert.pem ${ASSETSPATH}/cacert.pem
	@cp -R vendor/poetry-core/poetry/core/json/schemas ${ASSETSPATH}/schemas
	@cp -R vendor/poetry-core/poetry/core/version/grammars ${ASSETSPATH}/grammars
	@cp vendor/poetry-core/poetry/core/spdx/data/licenses.json ${ASSETSPATH}/licenses.json
	@cp vendor/virtualenv/src/virtualenv/activation/bash/activate.sh ${ASSETSPATH}/virtualenv/activation/activate.sh
	@cp vendor/virtualenv/src/virtualenv/activation/batch/activate.bat ${ASSETSPATH}/virtualenv/activation/activate.bat
	@cp vendor/virtualenv/src/virtualenv/activation/batch/deactivate.bat ${ASSETSPATH}/virtualenv/activation/deactivate.bat
	@cp vendor/virtualenv/src/virtualenv/activation/batch/pydoc.bat ${ASSETSPATH}/virtualenv/activation/pydoc.bat
	@cp vendor/virtualenv/src/virtualenv/activation/cshell/activate.csh ${ASSETSPATH}/virtualenv/activation/activate.csh
	@cp vendor/virtualenv/src/virtualenv/activation/fish/activate.fish ${ASSETSPATH}/virtualenv/activation/activate.fish
	@cp vendor/virtualenv/src/virtualenv/activation/powershell/activate.ps1 ${ASSETSPATH}/virtualenv/activation/activate.ps1
	@cp vendor/virtualenv/src/virtualenv/activation/python/activate_this.py ${ASSETSPATH}/virtualenv/activation/activate_this.py
	@cp vendor/virtualenv/src/virtualenv/activation/xonsh/activate.xsh ${ASSETSPATH}/virtualenv/activation/activate.xsh
	@cp vendor/virtualenv/src/virtualenv/create/debug.py ${ASSETSPATH}/virtualenv/debug.py
	@cp vendor/virtualenv/src/virtualenv/create/via_global_ref/_virtualenv.py ${ASSETSPATH}/virtualenv/_virtualenv.py
	@cp vendor/virtualenv/src/virtualenv/create/via_global_ref/builtin/python2/site.py ${ASSETSPATH}/virtualenv/site.py
	@cp vendor/virtualenv/src/virtualenv/discovery/py_info.py ${ASSETSPATH}/virtualenv/py_info.py
	@cp -R vendor/virtualenv/src/virtualenv/seed/wheels/embed ${ASSETSPATH}/virtualenv/wheels
	@cp static/packaging_tags.py ${ASSETSPATH}/packaging_tags.py

sign: _path_build _path_lib
	@codesign -s - ${BUILDPATH}/bin/poetry
	@find ${LIBPATH} -name '*.so' -type f | xargs -I $$ codesign -s - $$

pack_linux: ARCH := ${ARCH_LINUX}
pack_linux: TARGET := posix
pack_linux: pack

pack_mac: ARCH := ${ARCH_MAC}
pack_mac: TARGET := posix
pack_mac: pack

pack_win: ARCH := ${ARCH_WIN}
pack_win: TARGET := win
pack_win: pack

pack: _path_build clean_dist
	@mkdir -p dist
	@cd ${BUILDPATH} && tar -czvf poetry-bin-${BUILD_VERSION}-${ARCH}.tar.gz *
	@mv ${BUILDPATH}/poetry-bin-${BUILD_VERSION}-${ARCH}.tar.gz dist
	@openssl sha256 < dist/poetry-bin-${BUILD_VERSION}-${ARCH}.tar.gz | sed 's/^.* //' > dist/poetry-bin-${BUILD_VERSION}-${ARCH}.sha256sum
	@cat dist/poetry-bin-${BUILD_VERSION}-${ARCH}.sha256sum
