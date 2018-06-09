var forms = {};

forms.genForm = function(div) {

  div.html(''); // erase the div

  for(var i=0;i<5;i++) {
    var d = div.append('div');
    d.append('span').html('Name: ');
    d.append('input').attr('type', 'text');
  }

}
