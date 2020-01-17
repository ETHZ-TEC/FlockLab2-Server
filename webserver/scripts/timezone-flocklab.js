function unixtimestamp2tzstring(elem) {
  var x = $(elem).html()*1000;
  var date = new Date($(elem).html()*1000);
  var ofs=date.getTimezoneOffset();
  var ofh = Math.floor((Math.abs(ofs) / 60));
  var ofm = (Math.abs(ofs) % 60);
  var ts = (ofs<0?"+":"-")+(ofh<10?"0":"")+ofh+":"+(ofm<10?"0":"")+ofm;
  $(elem).html(date.getFullYear()+"-"+(date.getMonth()+1<10?"0":"")+(date.getMonth()+1)+"-"+(date.getDate()<10?"0":"")+date.getDate()+" "+(date.getHours()<10?"0":"")+date.getHours()+":"+(date.getMinutes()<10?"0":"")+date.getMinutes()+":"+(date.getSeconds()<10?"0":"")+date.getSeconds()+" "+ts);
  $(elem).show();
}

$(document).ready(function() {
  $(".time").each(function(){
      unixtimestamp2tzstring(this);
  });
});