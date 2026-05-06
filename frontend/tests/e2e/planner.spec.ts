import { expect, test } from '@playwright/test'

const planRecordsStorageKey = 'travelplanner.plan.records.v2'

const mockSseBody = [
  'data: {"type":"progress","message":"了解需求"}',
  '',
  'data: {"type":"agent_start","agentId":"orchestrator","label":"Orchestrator","status":"running","progress":12,"message":"开始拆解用户需求并生成检索参数"}',
  '',
  'data: {"type":"agent_done","agentId":"orchestrator","label":"Orchestrator","status":"completed","progress":100,"message":"已完成当前阶段处理"}',
  '',
  'data: {"type":"agent_start","agentId":"strategy_agent","label":"Strategy Planner","status":"running","progress":12,"message":"Strategy Planner已开始处理"}',
  '',
  'data: {"type":"agent_result","agentId":"strategy_agent","label":"Strategy Planner","status":"running","progress":86,"counts":{"days":3}}',
  '',
  'data: {"type":"agent_done","agentId":"strategy_agent","label":"Strategy Planner","status":"completed","progress":100,"message":"已完成当前阶段处理","counts":{"days":3}}',
  '',
  'data: {"type":"agent_start","agentId":"anchor_resolver_agent","label":"Anchor Resolver","status":"running","progress":12,"message":"Anchor Resolver已开始处理"}',
  '',
  'data: {"type":"agent_start","agentId":"weather_agent","label":"天气 Worker","status":"running","progress":12,"message":"天气 Worker已开始处理"}',
  '',
  'data: {"type":"agent_result","agentId":"weather_agent","label":"天气 Worker","status":"running","progress":86,"counts":{"days":1}}',
  '',
  'data: {"type":"weather","data":[{"date":"2026-03-10","day_weather":"晴","night_weather":"多云","day_temp":16,"night_temp":5,"wind_direction":"北风","wind_power":"3级"}]}',
  '',
  'data: {"type":"agent_done","agentId":"weather_agent","label":"天气 Worker","status":"completed","progress":100,"message":"已完成当前阶段处理","counts":{"days":1}}',
  '',
  'data: {"type":"agent_result","agentId":"anchor_resolver_agent","label":"Anchor Resolver","status":"running","progress":86,"counts":{"items":2}}',
  '',
  'data: {"type":"agent_done","agentId":"anchor_resolver_agent","label":"Anchor Resolver","status":"completed","progress":100,"message":"已完成当前阶段处理","counts":{"items":2}}',
  '',
  'data: {"type":"agent_start","agentId":"nearby_poi_agent","label":"Nearby POI Worker","status":"running","progress":12,"message":"Nearby POI Worker已开始处理"}',
  '',
  'data: {"type":"agent_result","agentId":"nearby_poi_agent","label":"Nearby POI Worker","status":"running","progress":86,"counts":{"attractions":2,"hotels":1,"restaurants":1}}',
  '',
  'data: {"type":"attractions","data":[{"name":"故宫博物院","address":"北京东城区景山前街4号","description":"宫廷建筑群","rating":4.8},{"name":"景山公园","address":"北京西城区景山西街44号","description":"俯瞰中轴线","rating":4.7}]}',
  '',
  'data: {"type":"hotels","data":[{"name":"王府井艺术酒店","address":"北京王府井","hotel_level":"舒适型","rating":4.5}]}',
  '',
  'data: {"type":"restaurants","data":[{"name":"四季民福","type":"dinner","description":"北京烤鸭","rating":4.6}]}',
  '',
  'data: {"type":"agent_done","agentId":"nearby_poi_agent","label":"Nearby POI Worker","status":"completed","progress":100,"message":"已完成当前阶段处理","counts":{"attractions":2,"hotels":1,"restaurants":1}}',
  '',
  'data: {"type":"agent_start","agentId":"route_matrix_agent","label":"Route Matrix","status":"running","progress":12,"message":"Route Matrix已开始处理"}',
  '',
  'data: {"type":"agent_result","agentId":"route_matrix_agent","label":"Route Matrix","status":"running","progress":86,"counts":{"routes":1}}',
  '',
  'data: {"type":"agent_done","agentId":"route_matrix_agent","label":"Route Matrix","status":"completed","progress":100,"message":"已完成当前阶段处理","counts":{"routes":1}}',
  '',
  'data: {"type":"agent_start","agentId":"itinerary_composer_agent","label":"Itinerary Composer","status":"running","progress":12,"message":"Itinerary Composer已开始处理"}',
  '',
  'data: {"type":"agent_result","agentId":"itinerary_composer_agent","label":"Itinerary Composer","status":"running","progress":86,"counts":{"days":1}}',
  '',
  'data: {"type":"agent_done","agentId":"itinerary_composer_agent","label":"Itinerary Composer","status":"completed","progress":100,"message":"已完成当前阶段处理","counts":{"days":1}}',
  '',
  'data: {"type":"agent_start","agentId":"final_planning","label":"Final Planner","status":"running","progress":12,"message":"Final Planner已开始处理"}',
  '',
  'data: {"type":"itinerary","data":{"city":"北京","start_date":"2026-03-10","end_date":"2026-03-12","total_days":3,"overall_suggestions":"先走中轴线，再往周边展开。","days":[{"date":"2026-03-10","day_index":1,"description":"宫城与城市开场","attractions":[{"name":"故宫博物院","address":"北京东城区景山前街4号","description":"宫廷建筑群","rating":4.8},{"name":"景山公园","address":"北京西城区景山西街44号","description":"俯瞰中轴线","rating":4.7}],"meals":[{"name":"四季民福","type":"dinner","description":"北京烤鸭","rating":4.6}],"weather":{"date":"2026-03-10","day_weather":"晴","night_weather":"多云","day_temp":16,"night_temp":5,"wind_direction":"北风","wind_power":"3级"},"hotel":{"name":"王府井艺术酒店","address":"北京王府井","hotel_level":"舒适型","rating":4.5},"estimated_cost":{"hotel":560,"meals":180,"transport":60}}],"weather_info":[{"date":"2026-03-10","day_weather":"晴","night_weather":"多云","day_temp":16,"night_temp":5,"wind_direction":"北风","wind_power":"3级"}],"restaurant_recommendations":[{"name":"四季民福","type":"dinner","description":"北京烤鸭","rating":4.6}],"statistics":{"attraction_count":2,"hotel_count":1,"restaurant_count":1},"important_notes":["上午尽量早点出发"],"packing_tips":["带一件轻薄外套"]}}',
  '',
  'data: {"type":"agent_done","agentId":"final_planning","label":"Final Planner","status":"completed","progress":100,"message":"已完成当前阶段处理","counts":{"days":1,"attractions":2}}',
  '',
  'data: {"type":"done"}',
  '',
].join('\n')

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/travel/health', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{"status":"ok"}',
    })
  })

  await page.route('**/api/v1/travel/plan', async (route) => {
    const request = route.request().postDataJSON() as Record<string, unknown>
    expect(request.duration).toBe(3)
    expect(request.days).toBeUndefined()

    await new Promise((resolve) => setTimeout(resolve, 300))
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: mockSseBody,
    })
  })
})

test('desktop planning flow works', async ({ page }) => {
  await page.goto('/')

  await page.getByLabel('目的地').fill('北京')
  await page.getByRole('button', { name: '立即开始规划' }).click()

  await expect(page).toHaveURL(/\/plan\//)
  await expect(page.getByRole('heading', { name: '北京' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '切换日程' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '故宫博物院', exact: true })).toBeVisible()
  await expect(page.getByText('四季民福').first()).toBeVisible()
})

test('opens result page when old local plan records exceed the write quota', async ({ page }) => {
  const quotaErrors: string[] = []

  page.on('pageerror', (error) => {
    if (error.message.includes('QuotaExceededError') || error.message.includes('exceeded the quota')) {
      quotaErrors.push(error.message)
    }
  })
  page.on('console', (message) => {
    const text = message.text()
    if (text.includes('QuotaExceededError') || text.includes('exceeded the quota')) {
      quotaErrors.push(text)
    }
  })

  await page.addInitScript(
    ({ storageKey, writeLimit }) => {
      const oldRecords = Object.fromEntries(
        Array.from({ length: 8 }, (_, index) => [
          `old-${index}`,
          {
            id: `old-${index}`,
            plan: {
              city: `旧行程${index}`,
              start_date: '2026-02-01',
              end_date: '2026-02-03',
              days: [],
              weather_info: [],
              narrative_plan: 'x'.repeat(6000),
            },
            request: {
              destination: `旧行程${index}`,
              start_date: '2026-02-01',
              end_date: '2026-02-03',
              duration: 3,
            },
            createdAt: new Date(2026, 1, index + 1).toISOString(),
          },
        ]),
      )
      const originalSetItem = Storage.prototype.setItem
      originalSetItem.call(window.localStorage, storageKey, JSON.stringify(oldRecords))

      Storage.prototype.setItem = function setItemWithQuota(key: string, value: string) {
        if (key === storageKey && value.length > writeLimit) {
          throw new DOMException('Quota exceeded', 'QuotaExceededError')
        }
        return originalSetItem.call(this, key, value)
      }
    },
    { storageKey: planRecordsStorageKey, writeLimit: 9000 },
  )

  await page.goto('/')
  await page.getByLabel('目的地').fill('北京')
  await page.getByRole('button', { name: '立即开始规划' }).click()

  await expect(page).toHaveURL(/\/plan\//)
  await expect(page.getByRole('heading', { name: '北京' })).toBeVisible()

  const storedRecords = await page.evaluate((storageKey) => {
    return JSON.parse(window.localStorage.getItem(storageKey) || '{}') as Record<string, { plan: { city: string } }>
  }, planRecordsStorageKey)
  const storedRecordIds = Object.keys(storedRecords)

  expect(storedRecordIds).toHaveLength(1)
  expect(storedRecords[storedRecordIds[0]]?.plan.city).toBe('北京')
  expect(quotaErrors).toEqual([])
})

test('mobile home layout remains usable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '开始规划行程' })).toBeVisible()
  await expect(page.getByRole('button', { name: '立即开始规划' })).toBeVisible()
})

test('home form inputs do not expose native borders or clip normal destination text', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/')

  const destinationInput = page.getByLabel('目的地')
  await destinationInput.fill('呼伦贝尔大草原')

  const inputBox = await destinationInput.evaluate((element) => {
    const input = element as HTMLInputElement
    const style = getComputedStyle(input)
    return {
      borderTopWidth: style.borderTopWidth,
      borderRightWidth: style.borderRightWidth,
      borderBottomWidth: style.borderBottomWidth,
      borderLeftWidth: style.borderLeftWidth,
      outlineStyle: style.outlineStyle,
      clientWidth: input.clientWidth,
      scrollWidth: input.scrollWidth,
    }
  })

  expect(inputBox).toMatchObject({
    borderTopWidth: '0px',
    borderRightWidth: '0px',
    borderBottomWidth: '0px',
    borderLeftWidth: '0px',
    outlineStyle: 'none',
  })
  expect(inputBox.scrollWidth).toBeLessThanOrEqual(inputBox.clientWidth)
})

test('desktop result page keeps the map dominant without fog overlays', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')

  await page.getByLabel('目的地').fill('北京')
  await page.getByRole('button', { name: '立即开始规划' }).scrollIntoViewIfNeeded()
  await page.getByRole('button', { name: '立即开始规划' }).click()

  await expect(page).toHaveURL(/\/plan\//)
  await expect(page.getByRole('heading', { name: '北京' })).toBeVisible()

  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0)

  const sidePanelWidth = await page.locator('aside').first().evaluate((element) => {
    return Math.round(element.getBoundingClientRect().width)
  })
  expect(sidePanelWidth).toBeLessThanOrEqual(400)

  const fogOverlayCount = await page.evaluate(() => {
    return [...document.querySelectorAll<HTMLElement>('*')].filter((element) => {
      const style = getComputedStyle(element)
      const rect = element.getBoundingClientRect()
      const coversViewport = rect.width >= window.innerWidth * 0.9 && rect.height >= window.innerHeight * 0.9
      const isOverlay = (style.position === 'absolute' || style.position === 'fixed') && style.pointerEvents === 'none'
      const background = style.backgroundImage
      const isFogGradient =
        background.includes('rgba(248, 250, 252') || background.includes('rgba(255, 255, 255, 0.24)')
      return coversViewport && isOverlay && isFogGradient
    }).length
  })

  expect(fogOverlayCount).toBe(0)
  await expect(page.getByText('Current Day')).toBeHidden()
})

test('desktop result side panel keeps controls, tags, and active day details readable', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto('/')

  await page.getByLabel('目的地').fill('北京')
  await page.getByRole('button', { name: '立即开始规划' }).click()

  await expect(page).toHaveURL(/\/plan\//)
  const panel = page.getByTestId('trip-layout-side-panel')
  await expect(panel).toBeVisible()

  const panelBackground = await panel.evaluate((element) => getComputedStyle(element).backgroundColor)
  expect(panelBackground).toBe('rgb(255, 255, 255)')

  const backButton = page.getByRole('button', { name: '返回首页' })
  const backButtonLayout = await backButton.evaluate((element) => {
    const style = getComputedStyle(element)
    return {
      whiteSpace: style.whiteSpace,
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight,
    }
  })
  expect(backButtonLayout.whiteSpace).toBe('nowrap')
  expect(backButtonLayout.scrollWidth).toBeLessThanOrEqual(backButtonLayout.clientWidth)
  expect(backButtonLayout.scrollHeight).toBeLessThanOrEqual(backButtonLayout.clientHeight)

  const activeDaySummary = panel.getByTestId('active-day-summary')
  const daySwitcher = panel.getByTestId('day-switcher')
  await expect(activeDaySummary).toBeVisible()
  await expect(daySwitcher).toBeVisible()

  const ordering = await panel.evaluate((element) => {
    const summary = element.querySelector('[data-testid="active-day-summary"]')?.getBoundingClientRect()
    const switcher = element.querySelector('[data-testid="day-switcher"]')?.getBoundingClientRect()
    return {
      summaryTop: summary?.top ?? 0,
      switcherTop: switcher?.top ?? 0,
    }
  })
  expect(ordering.summaryTop).toBeLessThan(ordering.switcherTop)
})

test.describe('mobile result page', () => {
  test.use({
    viewport: { width: 430, height: 900 },
    isMobile: true,
    hasTouch: true,
  })

  test('allows the result detail sheet to scroll with touch', async ({ page }) => {
    await page.goto('/')

    await page.getByLabel('目的地').fill('北京')
    await page.getByRole('button', { name: '立即开始规划' }).click()
    await expect(page).toHaveURL(/\/plan\//)

    const sheetScroller = page.locator('section.fixed div.overflow-y-auto').last()
    await expect(sheetScroller).toBeVisible()
    await expect
      .poll(() => sheetScroller.evaluate((element) => element.scrollHeight > element.clientHeight))
      .toBe(true)

    const box = await sheetScroller.boundingBox()
    expect(box).not.toBeNull()

    const client = await page.context().newCDPSession(page)
    const x = Math.round((box?.x || 0) + (box?.width || 0) / 2)
    const startY = Math.round((box?.y || 0) + (box?.height || 0) * 0.78)

    await client.send('Input.dispatchTouchEvent', {
      type: 'touchStart',
      touchPoints: [{ x, y: startY }],
    })
    await client.send('Input.dispatchTouchEvent', {
      type: 'touchMove',
      touchPoints: [{ x, y: startY - 260 }],
    })
    await client.send('Input.dispatchTouchEvent', {
      type: 'touchEnd',
      touchPoints: [],
    })

    await expect.poll(() => sheetScroller.evaluate((element) => element.scrollTop)).toBeGreaterThan(0)
  })
})
