// corporate_booking.js

// Global variables
let routeMap, modalMap;
let modalMarker;
let geocoder, directionsService, directionsRenderer;
let currentCity = '';
let currentLocationType = '';
let selectedLocation = null;

// Initialize maps when Google Maps API is loaded
function initMap() {
    // Show loading indicator
    document.getElementById('loadingIndicator').style.display = 'flex';
    document.querySelector('.form-container').style.display = 'none';
    document.getElementById('serviceAlert').style.display = 'none';
    
    geocoder = new google.maps.Geocoder();
    directionsService = new google.maps.DirectionsService();
    directionsRenderer = new google.maps.DirectionsRenderer();
    
    // Initialize with first city's coordinates or default
    const defaultCity = document.getElementById('city').options[0];
    const fallback = { 
        lat: parseFloat(defaultCity.dataset.lat) || 28.6139, 
        lng: parseFloat(defaultCity.dataset.lng) || 77.2090 
    };
    
    loadMaps(fallback);
    checkServiceAvailability(defaultCity.value);
}

function checkServiceAvailability(cityName) {
    // Update loading message
    document.querySelector('#loadingIndicator p').textContent = `Checking service availability in ${cityName}...`;
    
    fetch(`/corporate/book_ride/?city=${encodeURIComponent(cityName)}`, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) throw new Error('Network response was not ok');
        return response.json();
    })
    .then(data => {
        // Hide loading indicator
        document.getElementById('loadingIndicator').style.display = 'none';
        
        const serviceAlert = document.getElementById('serviceAlert');
        const formContainer = document.querySelector('.form-container');
        
        if (data.service_available) {
            serviceAlert.style.display = 'none';
            formContainer.style.display = 'block';
            
            // Update vehicle type dropdown
            const vehicleSelect = document.getElementById('vehicle_type');
            vehicleSelect.innerHTML = data.vehicle_types.map(vt => 
                `<option value="${vt.id}" data-price-per-km="${vt.price_per_km}">
                    ${vt.name} (₹${vt.price_per_km}/km)
                </option>`
            ).join('');
            
            // Center map on selected city
            const selectedCity = document.getElementById('city');
            const selectedOption = selectedCity.options[selectedCity.selectedIndex];
            const cityCenter = {
                lat: parseFloat(selectedOption.dataset.lat),
                lng: parseFloat(selectedOption.dataset.lng)
            };
            routeMap.setCenter(cityCenter);
            modalMap.setCenter(cityCenter);
        } else {
            document.getElementById('currentCityDisplay').textContent = data.current_city || cityName;
            serviceAlert.style.display = 'block';
            formContainer.style.display = 'none';
        }
    })
    .catch(error => {
        console.error('Error checking service availability:', error);
        // Hide loading and show form with default options
        document.getElementById('loadingIndicator').style.display = 'none';
        document.querySelector('.form-container').style.display = 'block';
    });
}

function loadMaps(center) {
    // Initialize route map (main form)
    routeMap = new google.maps.Map(document.getElementById('route_map'), {
      center,
      zoom: 13
    });
    directionsRenderer.setMap(routeMap);

    // Initialize modal map (will be shown when needed)
    modalMap = new google.maps.Map(document.getElementById('modalMap'), {
      center,
      zoom: 13
    });

    // Add click listener to modal map
    modalMap.addListener('click', function(event) {
      handleMapClick(event.latLng);
    });

    // Initialize autocomplete for modal search
    const searchInput = document.getElementById('modalLocationSearch');
    const autocomplete = new google.maps.places.Autocomplete(searchInput, {
      types: ['geocode'],
    });

    autocomplete.addListener('place_changed', function() {
      const place = autocomplete.getPlace();
      if (place.geometry) {
        modalMap.setCenter(place.geometry.location);
        if (modalMarker) modalMarker.setMap(null);
        modalMarker = new google.maps.Marker({
          position: place.geometry.location,
          map: modalMap
        });
        selectedLocation = {
          address: place.formatted_address,
          lat: place.geometry.location.lat(),
          lng: place.geometry.location.lng()
        };
      }
    });
}

function handleMapClick(latLng) {
    geocoder.geocode({ location: latLng }, (results, status) => {
      if (status === 'OK' && results[0]) {
        const address = results[0].formatted_address;

        const foundCity = results[0].address_components.find(
          c => c.types.includes('locality') || c.types.includes('administrative_area_level_2')
        );

        if (foundCity && foundCity.long_name !== currentCity) {
          alert("Please select a location within " + currentCity);
          return;
        }

        if (modalMarker) modalMarker.setMap(null);
        modalMarker = new google.maps.Marker({
          position: latLng,
          map: modalMap
        });

        selectedLocation = {
          address: address,
          lat: latLng.lat(),
          lng: latLng.lng()
        };
      }
    });
}

// Modal functions
function openLocationModal(type, element = null) {
    currentLocationType = type;
    document.getElementById('modalTitle').textContent = `Select ${type === 'from' ? 'Pickup' : type === 'to' ? 'Drop' : 'Stop'} Location`;
    document.getElementById('modalLocationSearch').value = '';
    
    // For stops, we need to get the parent container
    let container = null;
    if (type === 'stop') {
        container = element.closest('.stop-item');
    }
    
    // Center modal map on current selection if exists
    let currentLat, currentLng;
    
    if (type === 'stop' && container) {
        currentLat = parseFloat(container.querySelector('input[name="stops_lat[]"]').value);
        currentLng = parseFloat(container.querySelector('input[name="stops_lng[]"]').value);
    } else {
        currentLat = parseFloat(document.getElementById(`${type}_latitude`).value);
        currentLng = parseFloat(document.getElementById(`${type}_longitude`).value);
    }
    
    if (currentLat && currentLng) {
      const currentLocation = new google.maps.LatLng(currentLat, currentLng);
      modalMap.setCenter(currentLocation);
      if (modalMarker) modalMarker.setMap(null);
      modalMarker = new google.maps.Marker({
        position: currentLocation,
        map: modalMap
      });
    }
    
    document.getElementById('locationModal').classList.add('active');
}

function closeLocationModal() {
    document.getElementById('locationModal').classList.remove('active');
    selectedLocation = null;
}

function saveSelectedLocation() {
    if (selectedLocation) {
        if (currentLocationType === 'stop') {
            // Find the active stop container (the one that opened the modal)
            const stopItems = document.querySelectorAll('.stop-item');
            let activeStop = null;
            
            stopItems.forEach(item => {
                if (item.querySelector('.btn-select-location').getAttribute('onclick').includes(currentLocationType)) {
                    activeStop = item;
                }
            });
            
            if (activeStop) {
                activeStop.querySelector('input[name="stops[]"]').value = selectedLocation.address;
                activeStop.querySelector('input[name="stops_lat[]"]').value = selectedLocation.lat;
                activeStop.querySelector('input[name="stops_lng[]"]').value = selectedLocation.lng;
            }
        } else {
            document.getElementById(`${currentLocationType}_location`).value = selectedLocation.address;
            document.getElementById(`${currentLocationType}_latitude`).value = selectedLocation.lat;
            document.getElementById(`${currentLocationType}_longitude`).value = selectedLocation.lng;
        }
        
        updateRoute();
        closeLocationModal();
    } else {
        alert("Please select a location on the map or from search results");
    }
}

function updateRoute() {
    const fromLat = parseFloat(document.getElementById('from_latitude').value);
    const fromLng = parseFloat(document.getElementById('from_longitude').value);
    const toLat = parseFloat(document.getElementById('to_latitude').value);
    const toLng = parseFloat(document.getElementById('to_longitude').value);

    if (fromLat && fromLng && toLat && toLng) {
        const origin = new google.maps.LatLng(fromLat, fromLng);
        const destination = new google.maps.LatLng(toLat, toLng);
        
        // Get all stops
        const stops = [];
        document.querySelectorAll('.stop-item').forEach((stop, index) => {
            const lat = parseFloat(stop.querySelector('input[name="stops_lat[]"]').value);
            const lng = parseFloat(stop.querySelector('input[name="stops_lng[]"]').value);
            if (lat && lng) {
                stops.push({
                    location: new google.maps.LatLng(lat, lng),
                    stopover: true
                });
            }
        });
        
        directionsService.route({
            origin: origin,
            destination: destination,
            waypoints: stops,
            travelMode: 'DRIVING',
            optimizeWaypoints: true
        }, function(response, status) {
            if (status === 'OK') {
                directionsRenderer.setDirections(response);
                
                // Calculate distance
                const route = response.routes[0];
                let distance = 0;
                route.legs.forEach(leg => {
                    distance += leg.distance.value;
                });
                distance = distance / 1000; // convert to km
                
                document.getElementById('distance_km').value = distance.toFixed(2);
                updatePrice();
            } else {
                console.error('Directions request failed due to ' + status);
            }
        });
    }
}

function addStop() {
    const container = document.getElementById('stops-list');
    const stopIndex = container.children.length;

    const stopDiv = document.createElement('div');
    stopDiv.className = 'stop-item';
    stopDiv.innerHTML = `
        <div class="location-input-container">
            <input type="text" name="stops[]" placeholder="Enter stop location"
                   class="input-style location-input" readonly>
            <button type="button" class="btn-select-location" onclick="openLocationModal('stop', this)">
                <i class="fas fa-map-marker-alt"></i> Select Location
            </button>
        </div>
        <input type="hidden" name="stops_lat[]" />
        <input type="hidden" name="stops_lng[]" />
        <button type="button" class="btn btn-danger btn-sm" onclick="removeStop(this)">Remove</button>
    `;
    container.appendChild(stopDiv);
}

function removeStop(btn) {
    btn.closest('.stop-item').remove();
    updateRoute();
}

function updatePrice() {
    const distance = parseFloat(document.getElementById('distance_km').value);
    if (isNaN(distance)) return;

    const vehicleSelect = document.getElementById('vehicle_type');
    const selectedOption = vehicleSelect.options[vehicleSelect.selectedIndex];
    const pricePerKm = parseFloat(selectedOption.dataset.pricePerKm);

    // You can add a base fare if needed
    const baseFare = 50; // Example base fare
    const estimatedPrice = baseFare + (distance * pricePerKm);
    document.getElementById('estimated_price').value = estimatedPrice.toFixed(2);
}

// Handle city change
function handleCityChange() {
    const citySelect = document.getElementById('city');
    const selectedOption = citySelect.options[citySelect.selectedIndex];
    currentCity = selectedOption.value;
    
    // Center map on selected city
    const cityCenter = {
        lat: parseFloat(selectedOption.dataset.lat),
        lng: parseFloat(selectedOption.dataset.lng)
    };
    routeMap.setCenter(cityCenter);
    modalMap.setCenter(cityCenter);
    
    checkServiceAvailability(currentCity);
}

// Initialize the form
document.addEventListener('DOMContentLoaded', function() {
    toggleScheduledTime();
    
    // Update price when vehicle type changes
    document.getElementById('vehicle_type').addEventListener('change', updatePrice);
    
    // Handle city change
    document.getElementById('city').addEventListener('change', handleCityChange);
});

function toggleScheduledTime() {
    const rideType = document.getElementById('ride_type').value;
    const scheduledTimeGroup = document.getElementById('scheduled-time-group');
    
    if (rideType === 'scheduled') {
        scheduledTimeGroup.style.display = 'block';
        // Set minimum datetime to current time
        const now = new Date();
        const offset = now.getTimezoneOffset() * 60000;
        const localISOTime = (new Date(now - offset)).toISOString().slice(0, 16);
        document.getElementById('scheduled_time').min = localISOTime;
    } else {
        scheduledTimeGroup.style.display = 'none';
        document.getElementById('scheduled_time').value = '';
    }
}