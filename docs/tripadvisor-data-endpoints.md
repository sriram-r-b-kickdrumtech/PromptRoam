# TripAdvisor Data API — Endpoints (for reference)

Host: `tripadvisor-data.p.rapidapi.com`. Use with `x-rapidapi-key` from env at runtime.

## General
- `GET` auto-complete
- `GET` languages
- `GET` currencies

## Hotels
- `GET` hotels/search/filter
- `GET` hotels/search
- `GET` hotels/search (by address or name)
- `GET` hotels/details
- `GET` hotels/details/media-gallery
- `GET` hotels/details/all-amenities
- `GET` hotels/details/offers
- `GET` hotels/details/reviews
- `GET` hotels/details/nearbyrestaurants
- `GET` hotels/details/nearbyattractions
- `GET` hotels/details/hotelareasection
- `GET` hotels/details/abouthotel

## Attraction
- `GET` attraction/filters
- `GET` attraction/search
- `GET` attraction/search (by address or name)
- `GET` attraction/details
- `GET` attraction/details/media-gallery
- `GET` attraction/details/reviews
- `GET` attraction/details/nearbyattractions
- `GET` attraction/details/nearbyrestaurants
- `GET` attraction/details/explore-the-area
- `GET` attraction/details/featured-experiences

## Restaurants
- `GET` restaurants/filters
- `GET` restaurants/search
- `GET` restaurants/search-by-location
- `GET` restaurants/details
- `GET` restaurants/details/reviews
- `GET` restaurants/details/media-gallery
- `GET` restaurants/details/nearbyrestaurants
- `GET` restaurants/details/nearbyattractions
- `GET` restaurants/details/the-area
- `GET` restaurants/details/get-about-restaurant

Use exact path and query params from RapidAPI Playground for each endpoint.
