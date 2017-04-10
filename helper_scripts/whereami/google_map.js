function init_map() {
    let center = { lat: 34.701150, lng: 135.496840 };
    let map = new google.maps.Map(document.getElementById('map'), {
        center: center,
        zoom: 14,
        clickableIcons: false
    });

    let position = new google.maps.Circle({
        strokeColor: '#0000FF',
        strokeOpacity: 1.0,
        strokeWeight: 2,
        fillOpacity: 0.0,
        clickable: false,
        map: map,
        center: center,
        radius: 10
    });
    let position2 = new google.maps.Circle({
        strokeColor: '#0000FF',
        strokeOpacity: 1.0,
        strokeWeight: 2,
        fillOpacity: 0.0,
        clickable: false,
        map: map,
        center: center,
        radius: 2500
    });

    let curr_lat = null;
    let curr_lng = null;
    
    function updateLocation(lat, lng) {
        curr_lat = lat;
        curr_lng = lng;

        position.setCenter(new google.maps.LatLng(lat, lng));
        position2.setCenter(new google.maps.LatLng(lat, lng));
    }

    function update() {
        $.get("/getpos", function(data) {
            if (data.status == "OK") {
                updateLocation(data.location.lat, data.location.lng);
            }
        }, "json");
    }

    setInterval(update, 500);

    let directionsService = new google.maps.DirectionsService;
    let directionsDisplay = new google.maps.DirectionsRenderer({
        preserveViewport: true
    });

    directionsDisplay.setMap(map);

    let setter = (function *() {
        let p = yield;
        let start = new google.maps.LatLng(p.lat(), p.lng());
        curr_lat = start.lat();
        curr_lng = start.lng();

        p = yield;
        let end = new google.maps.LatLng(p.lat(), p.lng());
        while(true) {
            calculateAndDisplayRoute(directionsService, directionsDisplay, start, end);
            p = yield;
            end = new google.maps.LatLng(p.lat(), p.lng());
            start = new google.maps.LatLng(curr_lat, curr_lng); 
        }
    })();

    setter.next();
    map.addListener('click', function(e) {
        setter.next(e.latLng);
    });

    function calculateAndDisplayRoute(directionsService, directionsDisplay, start, end) {
        directionsService.route({
            origin: start,
            destination: end,
            travelMode: google.maps.TravelMode.DRIVING
        }, function(response, status) {
            if (status === google.maps.DirectionsStatus.OK) {
                directionsDisplay.setDirections(response);

                let path = response.routes[0].overview_path.map(function(v) {
                    return { lat: v.lat(), lng: v.lng() };
                });

                $.ajax({
                    method: 'put',
                    contenttype: 'application/json; charset=utf-8',
                    datatype: 'json',
                    url: '/path',
                    data: JSON.stringify(path)
                }).done(function() {
                    console.log("PUT success");
                });
            } else {
                window.alert('Directions request failed due to ' + status);
            }
        });
    }
}
