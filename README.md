# World of bits

Contains environments written in Javascript that run in the browser. The
environments are defined over a 210x160 grid, similar to ATARI. The top 50
pixels are devoted to the query, making the "game area" of size 160x160 pixels.

The original readme can be found in /world-of-bits/README_original.md for setup instructions.

It is used to create a docker image which runs a chrome instance with an HTML page defining the environment for the agent.

#### Create own Mini-wob environment 

_Instructions for /world-of-bits/ folder_.

Create environment and register it:
- Add HTML file in world-of-bits/static/miniwob which includes method:
  ```
   window.onload = function() {
      genProblem(); // start things off on load immediately
      core.startEpisode(); // start episode with call to core library
    }
  ```
- Add it to world-of-bits/config.py in the global registry
- Add it to universe/universe/\__init__.py to be registered in the universe docker environment *(See [my cloned Universe repo](https://github.com/kaikun213/My_Universe) README for instructions to add remote runtime and environment in client)*
- Add it in world-of-bits/static/core/miniwob.js to be registered as gym environment
- Further information can be found in original world-of-bits/static/README.md

Build the docker image:
- Make sure to `make install` before for downloading the custom docker-buildtool (required) from openAI
- The docker image to build from is changed directly to the world-of-bits image, since the link to the original base is broken - the dockerfile could be drastly reduced, but it just updates for newer versions of e.g. selenium webdriver
- `make build` to build the image
- `make dev ENV=wob.mini.AnExperiment-v0` to run a specific environment. It can be connected to via VNC on localhost:5900
- `make push` to push a small change in files
- `make shell` to enter the image in the command shell and modify files
- For further information investigate the makefile
