# World of Bits

Contains environments written in Javascript that run in the browser. The
environments are defined over a 210x160 grid, similar to ATARI. The top 50
pixels are devoted to the query, making the "game area" of size 160x160 pixels.

Future plans include working with full screens.

### Creating new environments

Please see the `README.MD` within the `static` folder for more information about how to create new environments.

### To inspect environments

You can do this locally by opening up `index.html` inside `static` folder,
which links to all current environments.

Alternatively, build the docker container with `make build` and then run
with `make dev`. You can connect via VNC by using `open vnc://localhost:5900`.

* To use a specific environment, for example `VNCClickButton-v0`, do

```
make dev ENV=wob.ClickButton-v0
```

Demonstrations will be written to `/tmp/world-of-bits-demo` so if you get a permission error, make sure that you can write to that directory (from @jimfan)
```
chmod o+x /tmp/world-of-bits-demo -R
```

### Record demonstrations

Make sure you've compiled the docker container with `make build` and then
run `make demo`. Now you must connect via VNC to port `5899`, that is:
`open vnc://localhost:5899`. Connecting on port 5899 tells the program to
actually record. The recordings are saved inside /tmp/demo inside the docker
image, which as you can see in the `Makefile` we are binding with the `-v`
flag to `/tmp/world-of-bits-demo`. You can inspect these recordings using
scripts inside the `universe` repo. For instance, after clicking around in
the VNC session for a while, kill the job and then inside the `universe` codebase
do, for example:

```
./bin/vnc_playback.py -d /tmp/world-of-bits-demo/1475756807-3fw9pvzscy8tsw-1
```

of course, your exact folder with the recording will have a different name.
You'll be presented with a window showing the recording data.
