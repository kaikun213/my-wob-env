# To build with the old quay.io URL run:
#   	make URL=quay.io/openai/universe.world-of-bits build
# or whatever make target you want instead of 'build'

URL ?= docker.openai.com/universe.world-of-bits
QUAY_URL ?= quay.io/openai/universe.world-of-bits

OPTS =
ifdef ENV
	OPTS = -e $(ENV)
endif

ifndef PORT_OFFSET
      PORT_OFFSET = 0
endif

VNC_PROXY_PORT := $(shell echo 20000+${PORT_OFFSET} | bc)
REWARDER_PROXY_PORT := $(shell echo 20001+${PORT_OFFSET} | bc)
ENV_API_PORT := $(shell echo 20002+${PORT_OFFSET} | bc)

# database to cache traffic and store supervision in DATA mode.
ifndef TURK_DB
      # assume env is located on host.
      HOST_IP=$(shell ifconfig | grep -Eo 'inet (addr:)?([0-9]*\.){3}[0-9]*' | grep -Eo '([0-9]*\.){3}[0-9]*' | grep -v '127.0.0.1' | head -n 1)
      TURK_DB=$(HOST_IP):6379
endif

.PHONY: build

build:
	cat VERSION
	docker-buildtool build -t $(URL):$$(cat VERSION)
	docker tag $(URL):$$(cat VERSION) $(URL):latest
	docker tag $(URL):$$(cat VERSION) $(URL):$$(cat VERSION)-$$(git rev-parse --short HEAD)

	# build quay images
	# docker tag $(URL):$$(cat VERSION) $(QUAY_URL):$$(cat VERSION)
	# docker tag $(URL):$$(cat VERSION) $(QUAY_URL):latest
	# docker tag $(URL):$$(cat VERSION) $(QUAY_URL):$$(cat VERSION)-$$(git rev-parse --short HEAD)

compose:
	docker-compose down && docker-compose up

run:
	docker run -ti --rm --cap-add NET_ADMIN --cap-add SYS_ADMIN -p 5900:5900 -p 5899:5899 -p 15900:15900 -p 15899:15899 -p 6080:6080 $(URL):$$(cat VERSION) run $(OPTS)

devbox-run:
	docker run -p 21000:5900 --cap-add NET_ADMIN --cap-add SYS_ADMIN -ti $(URL):$$(cat VERSION) run $(OPTS)

dev:
	echo 'running version', $(VERSION)
	docker run \
	-e TURK_DB=$(TURK_DB) \
	-v $$(pwd)/../..:/app \
	-v /tmp/world-of-bits-demo:/tmp/demo \
	-p 5900:5900 -p 15900:15900 -p 5899:5899 -p 15899:15899 -p 8888:8888 \
	--cap-add NET_ADMIN --cap-add SYS_ADMIN --privileged -ti $(URL):$$(cat VERSION) \
	dev $(OPTS)

demo:
	docker run \
	-v /tmp/world-of-bits-demo/:/tmp/demo \
	-e TURK_DB=$(TURK_DB) \
	-p 21000:5899 \
	--cap-add NET_ADMIN --cap-add SYS_ADMIN -ti $(URL):$$(cat VERSION) \
	demonstration $(OPTS)

demo-dev:
	docker run \
	-e TURK_DB=$(TURK_DB) \
	-v $$(pwd)/../..:/app \
	-v /tmp/world-of-bits-demo/:/tmp/demo \
	-p 21000:5899 \
	--cap-add NET_ADMIN --cap-add SYS_ADMIN -ti $(URL):$$(cat VERSION) \
	demonstration $(OPTS)

demo-mounted:
	docker run \
	-p 21050:5899 \
	-v /tmp/completed-world-of-bits-demo/:/tmp/completed-demos/ \
	--cap-add NET_ADMIN --cap-add SYS_ADMIN -ti $(URL):$$(cat VERSION) \
	demonstration -e wob.mini.ClickShape-v0 $(OPTS)

turk:
	docker run  \
	-e TURK_DB=$(TURK_DB) \
	-v /tmp/world-of-bits-demo:/tmp/demo \
	-p ${VNC_PROXY_PORT}:5901 -p ${REWARDER_PROXY_PORT}:15899 -p ${ENV_API_PORT}:8889  \
	--cap-add NET_ADMIN --cap-add SYS_ADMIN -ti $(URL):$$(cat VERSION) \
	turk-dev $(OPTS)

turk-dev:
	docker run \
	-e TURK_DB=$(TURK_DB) \
	-v $$(pwd)/../..:/app \
	-v /tmp/world-of-bits-demo:/tmp/demo \
	-p ${VNC_PROXY_PORT}:5901 -p 5900:5900 -p 15900:15900 -p 5899:5899 -p ${REWARDER_PROXY_PORT}:15899 -p 8888:8888 -p ${ENV_API_PORT}:8889 \
	--cap-add NET_ADMIN --cap-add SYS_ADMIN -ti $(URL):$$(cat VERSION) \
	turk-dev $(OPTS)

shell:
	docker run \
	-e TURK_DB=$(TURK_DB) \
	-v $$(pwd)/../..:/app \
	-v /tmp/world-of-bits-demo:/tmp/demo \
	-p 5901:5901 -p 5900:5900 -p 15900:15900 -p 5899:5899 -p 15899:15899 -p 8888:8888 \
	--cap-add NET_ADMIN --cap-add SYS_ADMIN -ti $(URL):$$(cat VERSION) \
	shell $(OPTS)

submodules:
	git submodule foreach git pull origin master
	git submodule update --init --recursive

install:
	pip install -r requirements.txt

push: build
	cat VERSION
	docker push $(URL):latest
	docker push $(URL):$$(cat VERSION)
	docker push $(URL):$$(cat VERSION)-$$(git rev-parse --short HEAD)

	# docker push $(QUAY_URL):latest
	# docker push $(QUAY_URL):$$(cat VERSION)
	# docker push $(QUAY_URL):$$(cat VERSION)-$$(git rev-parse --short HEAD)

pull:
	docker pull $(URL):$$(cat VERSION)
