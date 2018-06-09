# ---
# setup: pip install -e .
# build_root: ../..
# ignore:
#  - universe/go-vncdriver
#  - universe-envs/world-of-bits/data/
#  - '**/.git'
# include:
#  - universe-envs/controlplane
#  - universe-envs/base/openai-tigervnc
#  - universe-envs/base/openai-setpassword
#  - universe-envs/world-of-bits
#  - {'path': 'gym-demonstration', 'git': 'git@github.com:openai/gym-demonstration.git', 'setup': 'pip install -e .'}
#  - {'path': 'universe', 'git': 'git@github.com:openai/universe.git', 'setup': 'pip install -e .'}
#  - universe-envs/base/openai-setpassword
# ---


# Based off
# https://github.com/jfrazelle/dockerfiles/blob/master/chrome/stable/Dockerfile
# and https://hub.docker.com/r/robcherry/docker-chromedriver/~/dockerfile/
#FROM docker.openai.com/universe.base:latest -> offline, so use original image
FROM quay.io/openai/universe.world-of-bits


# Need hicolor-icon-theme due to this same issue:
# https://github.com/dnschneid/crouton/issues/632
#
# For some reason tcc and make need to be installed after earlier packages -- otherwise
# get `configure: error: C compiler cannot create executables`. Probably an easy
# misconfiguration

RUN curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.deb.sh | bash \
  && apt-get install -y --no-install-recommends \
  awscli \
  build-essential \
  ca-certificates \
  cmake \
  curl \
  dnsutils \
  git \
  git-core \
  git-lfs \
  hicolor-icon-theme \
  htop \
  iptables \
  libvncserver-dev \
  ntp \
  ssh \
  unzip \

  && curl -sSL https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
  && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
  && apt-get update \
  && apt-get install -y --no-install-recommends google-chrome-stable \
  && apt-get install -y make golang cmake zlib1g-dev \
  && pip install "go-vncdriver>=0.1.14" boto glances \
  && echo "install dependencies for mitmproxy" \
  && apt-get install -y libnss3-tools python-pip python-dev libffi-dev libssl-dev libxml2-dev libxslt1-dev libjpeg8-dev zlib1g-dev g++ \
  && echo "cleaning up" \
  && rm -rf /root/.cache/pip \
  && apt-get purge -y golang\
  && apt-get -y autoremove \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# Install Chrome WebDriver
RUN CHROMEDRIVER_VERSION=`curl -sS https://chromedriver.storage.googleapis.com/LATEST_RELEASE` && \
    mkdir -p /opt/chromedriver-$CHROMEDRIVER_VERSION && \
    curl -sS -o /tmp/chromedriver_linux64.zip https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip && \
    unzip -qq -o /tmp/chromedriver_linux64.zip -d /opt/chromedriver-$CHROMEDRIVER_VERSION && \
    rm /tmp/chromedriver_linux64.zip && \
    chmod +x /opt/chromedriver-$CHROMEDRIVER_VERSION/chromedriver && \
    ln -fs /opt/chromedriver-$CHROMEDRIVER_VERSION/chromedriver /usr/local/bin/chromedriver

# Disable the SUID sandbox so that Chrome can launch without being in a privileged container.
# One unfortunate side effect is that `google-chrome --help` will no longer work.
RUN dpkg-divert --add --rename --divert /opt/google/chrome/google-chrome.real /opt/google/chrome/google-chrome && \
    echo "#!/bin/bash\nexec /opt/google/chrome/google-chrome.real --disable-setuid-sandbox \"\$@\"" > /opt/google/chrome/google-chrome && \
    chmod 755 /opt/google/chrome/google-chrome

############# GYM AND VNC #################

RUN pip install autobahn PyYAML tornado pexpect

# Install TF
RUN pip install https://storage.googleapis.com/tensorflow/linux/cpu/tensorflow-0.11.0rc0-cp35-cp35m-linux_x86_64.whl && rm -rf /root/.cache/pip
RUN pip install "libvncdriver>=0.36.1" && rm -rf /root/.cache/pip

# Set up /app directory
COPY universe/setup.py /app/universe/setup.py
RUN pip install -e /app/universe && rm -rf /root/.cache/pip

# Copy just the setup.py to make best use of Docker caching
COPY universe-envs/world-of-bits/setup.py /app/universe-envs/world-of-bits/setup.py
RUN pip install -e /app/universe-envs/world-of-bits && rm -rf /root/.cache/pip

# Install service_identity to suppress annoying warning
COPY universe-envs/controlplane/setup.py /app/universe-envs/controlplane/setup.py
RUN pip install -e /app/universe-envs/controlplane service_identity

COPY gym-demonstration/setup.py /app/gym-demonstration/setup.py
COPY gym-demonstration/VERSION /app/gym-demonstration/VERSION
RUN pip install -e /app/gym-demonstration && rm -rf /root/.cache/pip

ENV DISPLAY=:0
# Force the container to use the go vnc driver
ENV UNIVERSE_VNCDRIVER=go
# Allows htop/glances to work
ENV TERM=xterm
ENV COMPLETED_DEMONSTRATION_DIR='/tmp/completed-demos/'
ENV PATH=$PATH:/app/universe-envs/world-of-bits/bin

# Grab the actual current Gym code (ALREADY IN IMAGE)
# RUN git clone --branch master --depth 1 https://github.com/openai/gym /usr/local/gym  \
#     && pip install -e /usr/local/gym \
#     && rm -rf /root/.cache/pip

COPY universe-envs/world-of-bits/realwob/.mitmproxy /app/universe-envs/world-of-bits/realwob/.mitmproxy
COPY universe-envs/world-of-bits/realwob/.pki /app/universe-envs/world-of-bits/realwob/.pki

# Install mitmproxy (ALREADY IN IMAGE)
# RUN git clone --branch master --depth 1 https://github.com/openai/mitmproxy /usr/local/mitmproxy \
#     && pip install -e /usr/local/mitmproxy \
#     && rm -rf /root/.cache/pip \
#     && cp -r /app/universe-envs/world-of-bits/realwob/.mitmproxy ~/ \
#     && cp -r /app/universe-envs/world-of-bits/realwob/.pki ~/ \
#     && certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n "mitmproxy" -i ~/.mitmproxy/mitmproxy-ca.pem \
#     && certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n "mitmproxy" -i ~/.mitmproxy/mitmproxy-ca-cert.pem
RUN  cp -r /app/universe-envs/world-of-bits/realwob/.mitmproxy ~/ \
     && cp -r /app/universe-envs/world-of-bits/realwob/.pki ~/ \
     && certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n "mitmproxy" -i ~/.mitmproxy/mitmproxy-ca.pem \
     && certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n "mitmproxy" -i ~/.mitmproxy/mitmproxy-ca-cert.pem

WORKDIR /app
COPY . /app

ENTRYPOINT ["/app/universe-envs/world-of-bits/init"]
CMD ["run"]
