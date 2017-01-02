function init_map() {
    var map = L.map('map').setView([35.68466, 139.73523], 16);

    L.tileLayer('http://{s}.tile.osm.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="http://osm.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    var position = null;

    function updateLocation(lat, lng) {
        if (position != null) {
            map.removeLayer(position);
        }
        position = L.circle([lat, lng], 5);
        map.addLayer(position);
        map.setView([lat, lng]);
    }

    function update() {
        $.get("/getpos", function(data) {
            updateLocation(data.location.lat, data.location.lng)
        }, "json" );
    }

    setInterval(update, 500);

    //-------
    let setter = (function *() {
        let control = L.Routing.control({
        }).addTo(map);

        control.on('routesfound', function(e) {
            console.log(e.routes);
            let route = e.routes[0];
            //for (let v of route.coordinates) {
                //L.marker([v.lat, v.lng]).addTo(map);
            //}
            $.ajax({
                method: "PUT",
                url: "/path",
                data: JSON.stringify(route.coordinates)
            }).done(function() {
            });
        });

        let waypoints = [];
        while(true) {
            waypoints.push(yield);
            control.spliceWaypoints(0, 2);

            waypoints.push(yield);
            control.setWaypoints(waypoints);
            waypoints = [];
        }
    })();

    setter.next();
    map.on('click', function (e) {
        //console.log(e);
        setter.next(e.latlng);
    });
}

$(document).ready(init_map)
