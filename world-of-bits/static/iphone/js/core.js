
var core = {}

// various common utilities

core.randi = function(min, max) { 
  return Math.floor(Math.random()*(max-min)+min);
}

core.randf = function(min, max) {
  return Math.random()*(max-min)+min;
}

core.sample = function(lst) {
  var ix = core.randi(0,lst.length);
  return lst[ix];
}

core.rand_color = function(min, max) {
  if(min == null) min = 0;
  if(max == null) max = 256;
  return 'rgba(' + core.randi(min, max) + ',' + core.randi(min, max) + ',' + core.randi(min, max) + ',1)';
}

// https://stackoverflow.com/questions/2450954/how-to-randomize-shuffle-a-javascript-array
core.shuffle = function(array) {
  var currentIndex = array.length, temporaryValue, randomIndex;

  // While there remain elements to shuffle...
  while (0 !== currentIndex) {

    // Pick a remaining element...
    randomIndex = Math.floor(Math.random() * currentIndex);
    currentIndex -= 1;

    // And swap it with the current element.
    temporaryValue = array[currentIndex];
    array[currentIndex] = array[randomIndex];
    array[randomIndex] = temporaryValue;
  }

  return array;
}


// utilities for timing episodes
var WOB_REWARD_GLOBAL = 0; // what was reward in previous iteration?
var WOB_DONE_GLOBAL = false; // a done indicator
var EPISODE_MAX_TIME = 5000; // in ms

// https://stackoverflow.com/questions/3169786/clear-text-selection-with-javascript
// this piece of code clears the selection in a new episode, if a user happened
// to select some part of text. We don't want this to persist across episodes
var clearUserSelection = function() {
  if (window.getSelection) {
    if (window.getSelection().empty) {  // Chrome
      window.getSelection().empty();
    } else if (window.getSelection().removeAllRanges) {  // Firefox
      window.getSelection().removeAllRanges();
    }
  } else if (document.selection) {  // IE?
    document.selection.empty();
  }
}

var EP_TIMER = null; // stores timer id
var ept0; // stores system time when episode begins (so we can time it)
var startEpisode = function() {
  clearUserSelection();
  ept0 = new Date().getTime();
  // start an end of episode timer
  if(EP_TIMER !== null) { clearTimeout(EP_TIMER); } // reset timer if needed
  EP_TIMER = setTimeout(function(){
    endEpisode(-1); // time ran out
  }, EPISODE_MAX_TIME);
}

var endEpisode = function(reward, time_proportional) {
  if(EP_TIMER !== null) { clearTimeout(EP_TIMER); } // stop timer.
  var ept1 = new Date().getTime(); // get system time

  // adjust reward based on time, so acting early is encouraged
  if(typeof time_proportional === 'undefined') { time_proportional = false; }
  if(time_proportional) {
    var dt = ept1 - ept0; // difference in ms since start of ep
    reward = reward * Math.max(0, 1.0 - dt/EPISODE_MAX_TIME);
  }

  WOB_REWARD_GLOBAL += reward; // add to global, to be accessed from Python
  WOB_DONE_GLOBAL = true;
  console.log('reward: ' + reward);
  // and lets go again
  genProblem();
  startEpisode();
}

// returns parameters passed in the url.
// e.g. ?topic=123&name=query+string in the url would return
// QueryString["topic"];    // 123
// QueryString["name"];     // query string
// QueryString["nothere"];  // undefined (object)
var QueryString = (function(a) {
  if (a == "") return {};
  var b = {};
  for (var i = 0; i < a.length; ++i)
  {
    var p=a[i].split('=', 2);
    if (p.length == 1)
      b[p[0]] = ""; 
    else
      b[p[0]] = decodeURIComponent(p[1].replace(/\+/g, " "));
  }
  return b;
})(window.location.search.substr(1).split('&'));

var getopt = function(d, k, def) {
  var v = d[k]
  return typeof v === 'undefined' ? def : v;
}
