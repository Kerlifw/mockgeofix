function init_map() {
    var map = L.map('map').setView([34.701150, 135.496840], 16);

    L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    var position = null;
    var curr_lat = null;
    var curr_lng = null;

    function updateLocation(lat, lng) {
        curr_lat = lat;
        curr_lng = lng;
        if (position != null) {
            map.removeLayer(position);
        }
        position = L.circle([lat, lng], 5);
        map.addLayer(position);
        //map.setView([lat, lng]);
    }

    function update() {
        $.get("/getpos", function(data) {
            if (data.status == "OK") {
                updateLocation(data.location.lat, data.location.lng)
            }
        }, "json" );
    }

    setInterval(update, 500);

    //-------
    let control = L.Routing.control({
        fitSelectedRoutes: false
    }).addTo(map);

    control.on('routesfound', function(e) {
        console.log(e.routes);
        let route = e.routes[0];
        //for (let v of route.coordinates) {
            //L.marker([v.lat, v.lng]).addTo(map);
        //}
        //
        $.ajax({
            method: 'PUT',
            contentType: 'application/json; charset=utf-8',
            dataType: 'json',
            url: '/path',
            data: JSON.stringify(route.coordinates)
        }).done(function() {
            console.log("PUT success");
        });
    });

    let setter = (function *() {
        let waypoints = [];
        let p = yield
        curr_lat = p.lat;
        curr_lng = p.lng;
        let marker = L.marker([curr_lat, curr_lng]).addTo(map);
        waypoints.push(p);
        waypoints.push(yield);
        map.removeLayer(marker)

        while(true) {
            control.spliceWaypoints(0, 2);
            control.setWaypoints(waypoints);
            p = yield
            waypoints = [{lat: curr_lat, lng: curr_lng}]
            waypoints.push(p);
        }
    })();

    setter.next();
    map.on('click', function (e) {
        //console.log(e);
        setter.next(e.latlng);
    });
}

$(document).ready(init_map)
