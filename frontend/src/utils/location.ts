import type { Location } from '@/types/travel'

export function isLocationAvailable(location?: Location | null): location is Location {
  return Boolean(
    location &&
      Number.isFinite(location.lat) &&
      Number.isFinite(location.lng),
  )
}

export function haversineKm(
  first?: Location | null,
  second?: Location | null,
): number | null {
  if (!isLocationAvailable(first) || !isLocationAvailable(second)) {
    return null
  }

  const toRadians = (value: number) => (value * Math.PI) / 180
  const earthRadiusKm = 6371
  const deltaLat = toRadians(second.lat - first.lat)
  const deltaLng = toRadians(second.lng - first.lng)
  const startLat = toRadians(first.lat)
  const endLat = toRadians(second.lat)

  const a =
    Math.sin(deltaLat / 2) ** 2 +
    Math.sin(deltaLng / 2) ** 2 * Math.cos(startLat) * Math.cos(endLat)

  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return earthRadiusKm * c
}

export function formatDistanceKm(distance?: number | null): string {
  if (typeof distance !== 'number' || !Number.isFinite(distance) || distance <= 0) {
    return '距离待补充'
  }

  if (distance < 1) {
    return `${Math.round(distance * 1000)} 米`
  }

  return `${distance.toFixed(distance > 20 ? 0 : 1)} km`
}

export function formatDuration(duration?: number): string {
  if (!duration) {
    return ''
  }

  if (duration >= 60) {
    const hours = Math.floor(duration / 60)
    const minutes = duration % 60
    return minutes > 0 ? `${hours}小时${minutes}分` : `${hours}小时`
  }

  return `${duration} 分钟`
}
