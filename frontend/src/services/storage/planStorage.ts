import type {
  DailyPlan,
  PlanningState,
  StoredPlanRecord,
  TripPlan,
  TripRequest,
} from '@/types/travel'

const STORAGE_KEY = 'travelplanner.plan.records.v2'
const DRAFT_KEY = 'travelplanner.plan.draft.v2'
const MAX_STORED_PLAN_RECORDS = 5

function readStorageMap(): Record<string, StoredPlanRecord> {
  if (typeof window === 'undefined') {
    return {}
  }

  const raw = window.localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return {}
  }

  try {
    return JSON.parse(raw) as Record<string, StoredPlanRecord>
  } catch {
    return {}
  }
}

function hydrateRecord(record?: StoredPlanRecord | null): StoredPlanRecord | null {
  if (!record) {
    return null
  }

  if (!record.planningState || record.planningState.itinerary) {
    return record
  }

  return {
    ...record,
    planningState: {
      ...record.planningState,
      itinerary: record.plan,
    },
  }
}

function stripMediaFields<T extends object>(item: T): T {
  const clone = { ...(item as Record<string, unknown>) }
  delete clone.photos
  delete clone.photo
  delete clone.image_url
  return clone as T
}

function stripOptionalMediaFields<T extends object>(item?: T): T | undefined {
  if (!item) {
    return undefined
  }
  return stripMediaFields(item)
}

function compactRouteSegment(segment: NonNullable<DailyPlan['route_segments']>[number]) {
  return {
    from_name: segment.from_name,
    to_name: segment.to_name,
    from_location: segment.from_location,
    to_location: segment.to_location,
    mode: segment.mode,
    distance: segment.distance,
    duration: segment.duration,
    cost: segment.cost,
  }
}

function compactPlan(plan: TripPlan): TripPlan {
  return {
    ...plan,
    days: plan.days.map((day) => ({
      ...day,
      hotel: stripOptionalMediaFields(day.hotel),
      attractions: (day.attractions || []).map((item) => stripMediaFields(item)),
      meals: (day.meals || []).map((item) => stripMediaFields(item)),
      route_segments: (day.route_segments || []).map((segment) => compactRouteSegment(segment)),
    })),
    restaurant_recommendations: (plan.restaurant_recommendations || []).map((item) => stripMediaFields(item)),
    transport: plan.transport
      ? {
          inter_city: plan.transport.inter_city,
          daily_plan: plan.transport.daily_plan,
          suggested_mode: plan.transport.suggested_mode,
          estimated_transport_cost: plan.transport.estimated_transport_cost,
          planning_reason: plan.transport.planning_reason,
        }
      : undefined,
  }
}

function compactPlanningState(state?: PlanningState): PlanningState | undefined {
  if (!state) {
    return undefined
  }

  return {
    ...state,
    messages: state.messages.slice(-12),
    eventLog: state.eventLog.slice(-24),
    agents: Object.fromEntries(
      Object.entries(state.agents).map(([agentId, agent]) => [
        agentId,
        {
          ...agent,
          logs: agent.logs.slice(-8),
        },
      ]),
    ) as PlanningState['agents'],
    attractions: state.attractions.map((item) => stripMediaFields(item)),
    hotels: state.hotels.map((item) => stripMediaFields(item)),
    restaurants: state.restaurants.map((item) => stripMediaFields(item)),
    routes: state.routes
      ? {
          inter_city: state.routes.inter_city,
          daily_plan: state.routes.daily_plan,
          suggested_mode: state.routes.suggested_mode,
          estimated_transport_cost: state.routes.estimated_transport_cost,
          planning_reason: state.routes.planning_reason,
        }
      : undefined,
    itinerary: undefined,
  }
}

function isQuotaExceededError(error: unknown): boolean {
  return (
    error instanceof DOMException &&
    (error.name === 'QuotaExceededError' || error.name === 'NS_ERROR_DOM_QUOTA_REACHED')
  )
}

function selectRecordsForWrite(
  records: Record<string, StoredPlanRecord>,
  currentId: string,
  maxRecords: number,
): Record<string, StoredPlanRecord> {
  const currentRecord = records[currentId]
  if (!currentRecord) {
    return {}
  }

  const selected: Record<string, StoredPlanRecord> = {
    [currentId]: currentRecord,
  }
  const remainingSlots = Math.max(0, maxRecords - 1)
  const previousRecords = Object.values(records)
    .filter((record) => record.id !== currentId)
    .sort((left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt))
    .slice(0, remainingSlots)

  for (const record of previousRecords) {
    selected[record.id] = record
  }
  return selected
}

function writeStorageMap(records: Record<string, StoredPlanRecord>): void {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(records))
}

function writeStorageMapWithQuota(records: Record<string, StoredPlanRecord>, currentId: string): void {
  for (let maxRecords = MAX_STORED_PLAN_RECORDS; maxRecords >= 1; maxRecords -= 1) {
    try {
      writeStorageMap(selectRecordsForWrite(records, currentId, maxRecords))
      return
    } catch (error) {
      if (!isQuotaExceededError(error)) {
        throw error
      }
      if (maxRecords === 1) {
        throw new Error('当前行程数据超过浏览器本地存储容量，无法保存结果。')
      }
    }
  }
}

export function createPlanId(): string {
  return `plan-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

export function savePlanRecord(
  plan: TripPlan,
  request: TripRequest,
  planningState?: PlanningState,
): string {
  const id = createPlanId()
  const records = readStorageMap()
  records[id] = {
    id,
    plan: compactPlan(plan),
    request,
    planningState: compactPlanningState(planningState),
    createdAt: new Date().toISOString(),
  }
  writeStorageMapWithQuota(records, id)
  return id
}

export function getPlanRecord(planId: string): StoredPlanRecord | null {
  return hydrateRecord(readStorageMap()[planId])
}

export function saveDraftRequest(request: TripRequest): void {
  if (typeof window === 'undefined') {
    return
  }

  window.sessionStorage.setItem(DRAFT_KEY, JSON.stringify(request))
}

export function readDraftRequest(): TripRequest | null {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.sessionStorage.getItem(DRAFT_KEY)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as TripRequest
  } catch {
    return null
  }
}

export function clearDraftRequest(): void {
  if (typeof window === 'undefined') {
    return
  }

  window.sessionStorage.removeItem(DRAFT_KEY)
}

function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function formatDate(value?: string): string {
  if (!value) {
    return ''
  }

  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }

  return parsed.toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  })
}

function formatMoney(value?: number): string {
  const amount = Number(value || 0)
  return amount > 0 ? `¥${Math.round(amount)}` : '待补充'
}

function formatDistance(value?: number): string {
  const distance = Number(value || 0)
  return distance > 0 ? `${distance.toFixed(distance >= 10 ? 1 : 1)} km` : '距离待补充'
}

function formatDuration(value?: number): string {
  const totalMinutes = Number(value || 0)
  if (totalMinutes <= 0) {
    return '时长待补充'
  }
  if (totalMinutes < 60) {
    return `${Math.round(totalMinutes)} 分钟`
  }
  const hours = Math.floor(totalMinutes / 60)
  const minutes = Math.round(totalMinutes % 60)
  return minutes ? `${hours}小时${minutes}分` : `${hours}小时`
}

function summarizeRoute(day: DailyPlan) {
  const segments = day.route_segments || []
  const distance = segments.reduce((sum, segment) => sum + Number(segment.distance || 0), 0)
  const duration = segments.reduce((sum, segment) => sum + Number(segment.duration || 0), 0)
  return {
    distance,
    duration,
  }
}

function renderList(items: string[], emptyText: string): string {
  if (!items.length) {
    return `<li class="empty">${escapeHtml(emptyText)}</li>`
  }

  return items
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join('')
}

function renderDayCard(day: DailyPlan): string {
  const route = summarizeRoute(day)
  const attractions = (day.attractions || []).map((item) => {
    const details = [item.category, item.rating ? `${item.rating.toFixed(1)} 分` : '', item.address]
      .filter(Boolean)
      .join(' · ')
    return `${item.name}${details ? ` · ${details}` : ''}`
  })
  const meals = (day.meals || []).map((item) => {
    const details = [
      item.meal_type || item.type,
      item.cuisine_type,
      item.price_per_person ? `人均 ${formatMoney(item.price_per_person)}` : '',
      item.address || '',
      item.meal_anchor_name && item.distance_to_anchor_km ? `距 ${item.meal_anchor_name} ${formatDistance(item.distance_to_anchor_km)}` : '',
    ]
      .filter(Boolean)
      .join(' · ')
    return `${item.name}${details ? ` · ${details}` : ''}`
  })
  const routePairs = (day.route_segments || []).map((segment) => {
    const details = [
      formatDistance(Number(segment.distance || 0)),
      formatDuration(Number(segment.duration || 0)),
    ].filter(Boolean).join(' · ')
    return `${segment.from_name} -> ${segment.to_name}${details ? ` · ${details}` : ''}`
  })
  const timeline = (day.timeline || []).map((item) => `${item.time} · ${item.activity}`)

  return `
    <section class="day-card">
      <div class="day-head">
        <div>
          <span class="day-index">DAY ${String(day.day_index).padStart(2, '0')}</span>
          <h2>${escapeHtml(day.description || `第 ${day.day_index} 天`)}</h2>
          <p class="day-date">${escapeHtml(formatDate(day.date))}</p>
        </div>
        <div class="day-metrics">
          <span>${escapeHtml(day.weather?.day_weather || '天气待补充')}</span>
          <span>${escapeHtml(formatDistance(route.distance))}</span>
          <span>${escapeHtml(formatDuration(route.duration))}</span>
          <span>${escapeHtml(formatMoney(
            Number(day.estimated_cost?.attractions || 0) +
            Number(day.estimated_cost?.meals || 0) +
            Number(day.estimated_cost?.transport || 0) +
            Number(day.estimated_cost?.hotel || 0),
          ))}</span>
        </div>
      </div>

      <div class="day-grid">
        <article class="panel">
          <h3>景点动线</h3>
          <ul>${renderList(attractions, '当天景点待补充')}</ul>
        </article>

        <article class="panel">
          <h3>住宿</h3>
          <p class="hotel-name">${escapeHtml(day.hotel?.name || day.accommodation || '酒店待补充')}</p>
          <p>${escapeHtml(day.hotel?.address || '')}</p>
          <p>${escapeHtml(day.hotel?.description || '')}</p>
        </article>

        <article class="panel">
          <h3>餐饮</h3>
          <ul>${renderList(meals, '当天餐饮待补充')}</ul>
        </article>

        <article class="panel">
          <h3>路径段</h3>
          <ul>${renderList(routePairs, '当前只保留景点之间的路径段')}</ul>
        </article>
      </div>

      <article class="panel timeline">
        <h3>执行时间线</h3>
        <ul>${renderList(timeline, '暂无时间线')}</ul>
      </article>
    </section>
  `
}

export function buildPlanHtmlDocument(plan: TripPlan): string {
  const noteItems = (plan.important_notes || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('')
  const packingItems = (plan.packing_tips || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('')
  const totalDays = plan.total_days || plan.days.length

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${escapeHtml(plan.city)} 行程</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #162235;
      --soft: #5c6674;
      --line: rgba(22, 34, 53, 0.12);
      --accent: #b35c3d;
      --accent-soft: rgba(179, 92, 61, 0.12);
      --paper: #f5f1e8;
      --panel: rgba(255, 255, 255, 0.88);
      --shadow: 0 18px 48px rgba(22, 34, 53, 0.08);
    }

    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, rgba(179, 92, 61, 0.12), transparent 26%),
        radial-gradient(circle at left center, rgba(58, 112, 104, 0.10), transparent 28%),
        linear-gradient(180deg, #f8f4ec 0%, #f2efe8 100%);
    }

    .page {
      width: min(1120px, calc(100vw - 48px));
      margin: 32px auto 56px;
    }

    .hero, .panel, .day-card {
      border: 1px solid var(--line);
      border-radius: 24px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }

    .hero {
      padding: 28px;
      display: grid;
      gap: 18px;
    }

    .eyebrow {
      color: var(--soft);
      font-size: 12px;
      letter-spacing: 0.18em;
      text-transform: uppercase;
    }

    h1, h2, h3, p {
      margin: 0;
    }

    .hero h1 {
      font-size: 40px;
      line-height: 1.04;
    }

    .hero-meta, .budget-row, .day-metrics {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }

    .chip {
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.9);
      border: 1px solid var(--line);
      color: var(--soft);
      font-size: 14px;
    }

    .summary-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
      margin-top: 18px;
    }

    .summary-grid .panel {
      padding: 18px;
      display: grid;
      gap: 10px;
    }

    .summary-grid ul,
    .day-card ul {
      margin: 0;
      padding-left: 18px;
      display: grid;
      gap: 8px;
    }

    .summary-grid li,
    .day-card li {
      color: var(--soft);
      line-height: 1.55;
    }

    .days {
      display: grid;
      gap: 18px;
      margin-top: 22px;
    }

    .day-card {
      padding: 22px;
      display: grid;
      gap: 18px;
    }

    .day-head {
      display: flex;
      justify-content: space-between;
      gap: 18px;
      align-items: flex-start;
    }

    .day-index {
      display: inline-block;
      color: var(--accent);
      font-size: 12px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      margin-bottom: 8px;
    }

    .day-date,
    .hotel-name,
    .overview-copy,
    .footer {
      color: var(--soft);
    }

    .day-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }

    .panel {
      padding: 18px;
      display: grid;
      gap: 10px;
    }

    .panel h3 {
      font-size: 18px;
    }

    .timeline {
      background: linear-gradient(180deg, rgba(255,255,255,0.92), rgba(248, 244, 236, 0.9));
    }

    .empty {
      list-style: none;
      margin-left: -18px;
      color: var(--soft);
    }

    .footer {
      margin-top: 18px;
      font-size: 13px;
      text-align: center;
    }

    @media print {
      body {
        background: white;
      }

      .page {
        width: 100%;
        margin: 0;
      }

      .hero, .panel, .day-card {
        box-shadow: none;
      }
    }

    @media (max-width: 900px) {
      .page {
        width: min(100vw - 24px, 100%);
        margin: 12px auto 28px;
      }

      .summary-grid,
      .day-grid {
        grid-template-columns: 1fr;
      }

      .day-head {
        flex-direction: column;
      }

      .hero h1 {
        font-size: 32px;
      }
    }
  </style>
</head>
<body>
  <main class="page">
    <section class="hero">
      <span class="eyebrow">TravelPlanner Export</span>
      <div>
        <h1>${escapeHtml(plan.city)} 行程</h1>
        <p class="overview-copy">${escapeHtml(plan.overall_suggestions || plan.narrative_plan || '已导出当前规划结果。')}</p>
      </div>
      <div class="hero-meta">
        <span class="chip">${escapeHtml(formatDate(plan.start_date))}</span>
        <span class="chip">${escapeHtml(formatDate(plan.end_date))}</span>
        <span class="chip">${escapeHtml(String(totalDays))} 天</span>
        <span class="chip">${escapeHtml(String(plan.statistics?.attraction_count || plan.days.flatMap((day) => day.attractions).length))} 个景点</span>
        <span class="chip">预算 ${escapeHtml(formatMoney(plan.estimated_total_cost))}</span>
      </div>

      <div class="summary-grid">
        <article class="panel">
          <h3>整体说明</h3>
          <p class="overview-copy">${escapeHtml(plan.narrative_plan || '暂无整体叙述')}</p>
        </article>
        <article class="panel">
          <h3>注意事项</h3>
          <ul>${noteItems || '<li class="empty">暂无补充说明</li>'}</ul>
        </article>
        <article class="panel">
          <h3>携带建议</h3>
          <ul>${packingItems || '<li class="empty">暂无补充说明</li>'}</ul>
        </article>
      </div>
    </section>

    <section class="days">
      ${plan.days.map((day) => renderDayCard(day)).join('')}
    </section>

    <p class="footer">导出时间：${escapeHtml(formatDate(new Date().toISOString()))}</p>
  </main>
</body>
</html>`
}

export function downloadPlanAsHtml(plan: TripPlan, filename: string): void {
  const blob = new Blob([buildPlanHtmlDocument(plan)], {
    type: 'text/html;charset=utf-8',
  })

  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  URL.revokeObjectURL(url)
}
