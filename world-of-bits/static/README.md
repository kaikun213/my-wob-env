Various environments for world of bits, written in Javascript and accessed via a browser.

# What is an environment? #

##### Interested in creating some environments for agents to interact with? Read on! #####

Environments (also referred to as tasks) are a certain set of actions an agent (human or computer) must do in a given period of time (also referred to as an episode). An environment consists of HTML, CSS and JavaScript. Imported JavaScript files should be stored locally within the `common/` folder and should not be stored online. Note that it's okay to import libraries for tasks — jQuery and D3.js are frequently used in these pre-existing environments. Environmental difficulty varies: actions required range from short and simple tasks such as clicking certain types of HTML elements, to more complicated tasks like booking a flight or deleting a file from a simulated terminal shell.

The environment should have a width of 160pixels and a height of 210pixels and be placed within the `#wrap` div. The `#query` div is 160px by 50px: this area is used to list the action that the agent must complete before the end of the episode. The `#area` div is 160px by 160px, and is where your interactive environment should be displayed. The `#reward-display` div is used to visually show agents their score as tasks are performed.

Once an episode is completed, you'll need to provide the agent some feedback in the form of a score / reward. A general ruleset for rewarding is to provide the agent a positive score for correctly completing a task, proportional to the amount of time it takes to complete the episode. Otherwise, the agent should receive a negative reward for performing the task incorrectly.

A simple example of an environment and its reward system can be found in `click-test.html`, where the agent receives a positive score based on the amout of time taken to click the button on the screen. A more complex example of an environment is `tic-tac-toe.html` where the agent receives a positive score for winning, and different negative scores on a tie or a loss.

# Creating new environments #

New environments should be placed in the `miniwob/` folder and referenced within `core/miniwobs.js`, which will dynamically add it to the index.html page. The environment must also be added to `universe-envs/world-of-bits/config.py` and `universe/__init__.py`, using the same environment ID used in `miniwobs.js`, in order to be picked up as part of the environment suite.

Most of the environments will have the following snippet that runs once the page has loaded:

    window.onload = function() {
      genProblem();
      core.startEpisode();
    }

`genProblem()` is called to generate a new, randomized instance of the problem, and `core.startEpisode()` is called to start a timed countdown for that episode.

When an agent has completed an episode, correctly or incorrectly, you can call `core.endEpisode(reward, [time_proportional])` to reward the agent a score, generate a new environment problem, and restart the episode timer. If the agent runs out of time, this function will be called automatically.

Note that the default time per episode is currently set to 10 seconds. You can override this by setting `core.EPISODE_MAX_TIME` in milliseconds, at the top of your javascript code (after you've imported core.js) in your environment.

# Libraries #

The following libraries are available for use and can be imported from the `core/` or `common/` folders:

## `core.js` (required) ##

This library is used to start and stop environment episodes, and reward an agent for each episode.

##### `core.startEpisode()`:
Starts a timed episode in the environment.

##### `core.endEpisode(reward, [time_proportional])`:
Ends the episode in the environment that's currently in progress. `reward` should be a number between -1 and 1, where -1 denotes a failed interaction and 1 denotes a correct interaction. `time_proportional` is a boolean that denotes whether or not the `reward` passed in should be adjusted based on the amount of time taken to complete the episode.

##### `core.EPISODE_MAX_TIME`:
The total time (in milliseconds) an agent has to attempt to solve a problem. Default time per episode is 10 seconds. Can override this in your environment to give the agent more (or less) time.

##### `core.randi(min, max)`:
Returns a random integer from `min` up to, but not including, `max`.

##### `core.randf(min, max)`:
Returns a random float from `min` up to, but not including, `max`.

##### `core.sample(list)`:
Given a list, returns a random element from that list.

##### `core.shuffle(list)`:
Given a list, returns the list with elements randomly shuffled.

## `ui_utils.js` ##

This library includes multiple variables and helper functions for doing assorted tasks such as generating random paragraphs of Lorem Ipsum or converting dates to user-friendly strings.

##### `ui_utils.COLORS`:
A list of CSS-usable colors.

##### `ui_utils.PEOPLE_NAMES`:
A list of hundreds of people names.

##### `ui_utils.LAST_NAMES`:
A list of hunderds of people's last names.

##### `ui_utils.COUNTRIES`:
A list of countries sorted in alphabetical order.

##### `ui_utils.FIFTY_NAMES`:
A short list containing 50 first names.

##### `ui_utils.toDateString(dateObj)`:
Returns a string in the format `'MM-DD-YYYY'`.

##### `ui_utils.randomDate(startDate, endDate)`:
Given two date objects, returns a date object with a randomized time between the two intervals.

##### `ui_utils.generateWords(minWords, [maxWords])`:
Returns a string with a random number of Lorem Ipsum words, with a length between `minWords` and `maxWords`.

##### `ui_utils.generateString(minChars, [maxChars])`:
Returns a string with a random number of characters, with a length between `minChars` and `maxChars`.

## `shapes.js` ##

This library is used for for generating and describing shapes/digits/letters in a grid that have various properties.

##### `shapes.genGrid(n)`:
Generates a grid of `n` random shapes that can be rendered on an SVG element.

##### `shapes.renderGrid(svg, grid)`:
Renders a `grid` of shapes onto the provided `svg` element.

##### `shapes.generalDesc(s)`:
Given a shape `s`, returns an object that describes the shape using various properties like size, color, and type.

##### `shapes.sampleDesc()`:
Returns a randomly generated shape description.

##### `shapes.shapeMatchesText(s, desc)`:
For a given shape `s`, returns a `boolean` denoting whether or not it matches the description `desc`.

##### `shapes.drag()`:
A D3 helper function that allows an agent to drag shapes around an SVG element.

##### `shapes.gridCoords(shape)`:
For a given shape, returns the x and y-coordinates within an SVG element.

##### `shapes.drawCircles(circles, grid)`:
Draws an array of `circles` onto an SVG `grid`. See the function for a list of available attributes.

##### `shapes.drawLines(lines, grid)`:
Draws an array of `lines` onto an SVG `grid`. See the function for a list of available attributes.
