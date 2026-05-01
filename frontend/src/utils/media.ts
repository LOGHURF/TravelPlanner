import type { Attraction, Hotel, Restaurant } from '@/types/travel'

export function getAttractionImage(attraction?: Attraction): string | undefined {
  return attraction?.image_url || attraction?.photo
}

export function getHotelImage(hotel?: Hotel): string | undefined {
  return hotel?.image_url
}

export function getRestaurantImage(restaurant?: Restaurant): string | undefined {
  return restaurant?.photo
}
