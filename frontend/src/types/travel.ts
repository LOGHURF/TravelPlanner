export interface TripRequest {
  destination: string
  start_date?: string
  end_date?: string
  duration?: number
  origin?: string
  num_people?: number
  companions?: '独自' | '家庭' | '情侣' | '朋友' | '老人'
  pace?: '紧凑' | '适中' | '宽松'
  style_preferences?: string[]
  hotel_level?: '经济型' | '舒适型' | '高档型' | '豪华型'
  preferences?: string[]
  special_requirements?: string
}

export interface Location {
  lat: number
  lng: number
}

export interface Attraction {
  name: string
  address: string
  location?: Location | null
  description?: string
  rating?: number
  category?: string
  tags?: string[]
  visit_duration?: string
  indoor?: boolean
  best_time?: string
  ticket_price?: number
  open_hours?: string
  phone?: string
  photo?: string
  image_url?: string
}

export interface Hotel {
  name: string
  address: string
  location?: Location | null
  description?: string
  rating?: number
  hotel_level?: string
  star_rating?: number
  price_per_night?: number
  total_price?: number
  distance_to_center?: string
  distance?: string
  amenities?: string[]
  phone?: string
  image_url?: string
}

export interface Restaurant {
  name: string
  type: 'breakfast' | 'lunch' | 'dinner' | 'snack'
  meal_type?: 'breakfast' | 'lunch' | 'dinner' | 'snack'
  address?: string
  location?: Location | null
  description?: string
  rating?: number
  estimated_cost?: number
  price_per_person?: number
  cuisine_type?: string
  is_recommended?: boolean
  meal_anchor_name?: string
  meal_anchor_role?: string
  distance_to_anchor_km?: number
  photo?: string
}

export interface TransportDayPlan {
  day_index: number
  hotel?: Hotel | null
  hotel_index?: number | null
  attractions?: Attraction[]
  attraction_indexes?: number[]
  meals?: Restaurant[]
  meal_indexes?: number[]
  reason?: string
}

export interface WeatherInfo {
  date: string
  day_weather: string
  night_weather: string
  day_temp: number
  night_temp: number
  wind_direction: string
  wind_power: string
  suggestion?: string
  uv_index?: string
  comfort_index?: string
}

export interface RouteSegment {
  from_name: string
  to_name: string
  from_location?: Location | null
  to_location?: Location | null
  mode?: string
  distance?: number
  duration?: number
  cost?: number
  instruction?: string
}

export interface TransportPlan {
  inter_city?: Record<string, unknown>
  daily_routes?: RouteSegment[][]
  daily_plan?: TransportDayPlan[]
  suggested_mode?: string
  estimated_transport_cost?: number
  planning_reason?: string
}

export interface TimelineItem {
  time: string
  activity: string
  type: 'attraction' | 'meal' | 'transport' | 'hotel'
}

export interface DailyPlan {
  date: string
  day_index: number
  day_of_week?: string
  description?: string
  weather?: WeatherInfo
  weather_note?: string
  accommodation?: string
  hotel?: Hotel
  arrival_transport?: {
    from_city?: string
    to_city?: string
    mode?: string
    summary?: string
  }
  attractions: Attraction[]
  meals: Restaurant[]
  route_segments?: RouteSegment[]
  transportation?: string
  transport_mode?: string
  estimated_cost?: {
    attractions?: number
    meals?: number
    transport?: number
    hotel?: number
    [key: string]: number | undefined
  }
  timeline?: TimelineItem[]
}

export interface TripPlan {
  city: string
  start_date: string
  end_date: string
  total_days?: number
  days: DailyPlan[]
  narrative_plan?: string
  weather_info: WeatherInfo[]
  restaurant_recommendations?: Restaurant[]
  budget_breakdown?: {
    hotel?: number
    attractions?: number
    meals?: number
    transport?: number
    [key: string]: number | undefined
  }
  total_budget?: number
  estimated_total_cost?: number
  budget_estimate_range?: {
    low?: number
    high?: number
  }
  transport?: TransportPlan
  overall_suggestions?: string
  packing_tips?: string[]
  important_notes?: string[]
  statistics?: {
    attraction_count?: number
    restaurant_count?: number
    hotel_count?: number
    [key: string]: number | undefined
  }
}

export type PlanningAgentId =
  | 'orchestrator'
  | 'strategy_agent'
  | 'anchor_resolver_agent'
  | 'nearby_poi_agent'
  | 'route_matrix_agent'
  | 'itinerary_composer_agent'
  | 'weather_agent'
  | 'plan_evaluator_agent'
  | 'final_planning'

export type PlanningAgentStatus = 'pending' | 'running' | 'completed' | 'error'

export interface PlanningAgentDefinition {
  id: PlanningAgentId
  label: string
  phase: 'prepare' | 'parallel' | 'refine' | 'enrich' | 'route' | 'evaluate' | 'repair' | 'finalize'
  weight: number
  description: string
}

export interface PlanningAgentState {
  id: PlanningAgentId
  label: string
  phase: PlanningAgentDefinition['phase']
  description: string
  status: PlanningAgentStatus
  progress: number
  logs: string[]
  counts: Record<string, number>
  lastMessage?: string
  startedAt?: string
  finishedAt?: string
}

export type PlanningEventType =
  | 'progress'
  | 'attractions'
  | 'hotels'
  | 'restaurants'
  | 'weather'
  | 'routes'
  | 'narrative'
  | 'itinerary'
  | 'agent_start'
  | 'agent_progress'
  | 'agent_result'
  | 'agent_done'
  | 'agent_error'
  | 'error'
  | 'done'

export interface PlanningProgress {
  type: PlanningEventType
  message?: string
  data?: unknown
  agentId?: PlanningAgentId
  label?: string
  phase?: PlanningAgentDefinition['phase']
  status?: PlanningAgentStatus
  progress?: number
  counts?: Record<string, number>
  timestamp?: string
}

export interface PlanningEventRecord {
  id: string
  eventType: PlanningEventType
  message: string
  timestamp?: string
  agentId?: PlanningAgentId
  label?: string
  phase?: PlanningAgentDefinition['phase']
  status?: PlanningAgentStatus
}

export interface PlanningResultHighlight {
  id: 'attractions' | 'hotels' | 'restaurants' | 'weather' | 'routes' | 'itinerary'
  label: string
  status: 'empty' | 'partial' | 'ready'
  count: number
  summary: string
  preview: string[]
}

export interface PlanningState {
  step: 'idle' | 'planning' | 'completed' | 'error'
  progress: number
  messages: string[]
  eventLog: PlanningEventRecord[]
  agents: Record<PlanningAgentId, PlanningAgentState>
  attractions: Attraction[]
  hotels: Hotel[]
  restaurants: Restaurant[]
  weather: WeatherInfo[]
  routes?: TransportPlan
  itinerary?: TripPlan
  error?: string
}

export interface StoredPlanRecord {
  id: string
  request: TripRequest
  plan: TripPlan
  planningState?: PlanningState
  createdAt: string
}
