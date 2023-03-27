$(function() {

  $( "#day_pick" ).on('input', function () {
    let nb_day = $(this).val()
    let shared = $('#isShared').is(':checked');
    price_calc(nb_day, shared)
  });

  $( "#isShared" ).on('change', function () {
    let nb_day = $( "#day_pick" ).val()
    let shared = $('#isShared').is(':checked');
    price_calc(nb_day, shared)
  });

  function price_calc(nb_day, shared) {
    let gb = nb_day * 6.5
    let reduction = 0;
    let price_day = 1.75;

    if(nb_day > 0 && nb_day < 8) {
      reduction = 0;
      price_day = 1.75;
    }
    if(nb_day > 7 && nb_day < 16) {
      reduction = 4;
      price_day = 1.68;
    }
    if(nb_day > 15 && nb_day < 23) {
      reduction = 8.57;
      price_day = 1.60;
    }
    if(nb_day > 22) {
      reduction = 17.14;
      price_day = 1.45;
    }

    let price = (nb_day * price_day).toFixed(2);

    $('#recap').html("<b>"+nb_day+"</b> Jours | <b>"+gb+"</b> Go | Réduction <b>"+reduction+"</b>% | <b>"+price+"</b> €");
  }

  price_calc(10, false)
});