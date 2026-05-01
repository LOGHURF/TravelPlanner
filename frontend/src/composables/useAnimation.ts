/**
 * useAnimation - 动画工具组合式函数
 * 
 * 提供页面动画、滚动动画、数字动画等功能
 */

import { ref, onMounted, onUnmounted, type Ref } from 'vue'

// Number animation
export function useCountUp(
  target: Ref<number> | number,
  duration: number = 1000,
  delay: number = 0
) {
  const displayValue = ref(0)
  const isAnimating = ref(false)
  
  let startTime: number | null = null
  let rafId: number | null = null
  const targetValue = typeof target === 'number' ? target : target.value
  
  function animate(currentTime: number) {
    if (!startTime) startTime = currentTime
    const elapsed = currentTime - startTime - delay
    
    if (elapsed < 0) {
      rafId = requestAnimationFrame(animate)
      return
    }
    
    const progress = Math.min(elapsed / duration, 1)
    // Ease out cubic
    const easeProgress = 1 - Math.pow(1 - progress, 3)
    displayValue.value = Math.round(targetValue * easeProgress)
    
    if (progress < 1) {
      rafId = requestAnimationFrame(animate)
    } else {
      isAnimating.value = false
    }
  }
  
  function start() {
    if (isAnimating.value) return
    isAnimating.value = true
    displayValue.value = 0
    startTime = null
    rafId = requestAnimationFrame(animate)
  }
  
  function stop() {
    if (rafId) {
      cancelAnimationFrame(rafId)
      rafId = null
    }
    isAnimating.value = false
  }
  
  onUnmounted(stop)
  
  return {
    displayValue,
    isAnimating,
    start,
    stop,
  }
}

// Scroll reveal animation
export function useScrollReveal(
  elementRef: Ref<HTMLElement | null>,
  options: {
    threshold?: number
    rootMargin?: string
    triggerOnce?: boolean
  } = {}
) {
  const { threshold = 0.1, rootMargin = '0px', triggerOnce = true } = options
  const isVisible = ref(false)
  const hasTriggered = ref(false)
  
  let observer: IntersectionObserver | null = null
  
  onMounted(() => {
    if (!elementRef.value) return
    
    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            isVisible.value = true
            if (triggerOnce) {
              hasTriggered.value = true
              observer?.unobserve(entry.target)
            }
          } else if (!triggerOnce) {
            isVisible.value = false
          }
        })
      },
      { threshold, rootMargin }
    )
    
    observer.observe(elementRef.value)
  })
  
  onUnmounted(() => {
    if (observer && elementRef.value) {
      observer.unobserve(elementRef.value)
    }
  })
  
  return {
    isVisible,
    hasTriggered,
  }
}

// Stagger animation for lists
export function useStaggerAnimation(
  itemCount: Ref<number> | number,
  options: {
    staggerDelay?: number
    initialDelay?: number
  } = {}
) {
  const { staggerDelay = 50, initialDelay = 0 } = options
  const visibleItems = ref<boolean[]>([])
  const count = typeof itemCount === 'number' ? itemCount : itemCount.value
  
  function start() {
    visibleItems.value = new Array(count).fill(false)
    
    for (let i = 0; i < count; i++) {
      setTimeout(() => {
        visibleItems.value[i] = true
      }, initialDelay + i * staggerDelay)
    }
  }
  
  function reset() {
    visibleItems.value = new Array(count).fill(false)
  }
  
  return {
    visibleItems,
    start,
    reset,
  }
}

// Page transition
export function usePageTransition() {
  const isEntering = ref(false)
  const isLeaving = ref(false)
  
  function onEnter() {
    isEntering.value = true
    setTimeout(() => {
      isEntering.value = false
    }, 500)
  }
  
  function onLeave() {
    isLeaving.value = true
  }
  
  return {
    isEntering,
    isLeaving,
    onEnter,
    onLeave,
  }
}

// Spring animation utility
export function springAnimation(
  from: number,
  to: number,
  stiffness: number = 100,
  damping: number = 10
) {
  let velocity = 0
  let current = from
  const target = to
  
  return {
    update(): number {
      const displacement = current - target
      const springForce = -stiffness * displacement
      const dampingForce = -damping * velocity
      const acceleration = springForce + dampingForce
      
      velocity += acceleration * 0.016 // ~60fps
      current += velocity * 0.016
      
      return current
    },
    getCurrent(): number {
      return current
    },
    isSettled(epsilon: number = 0.01): boolean {
      return Math.abs(current - target) < epsilon && Math.abs(velocity) < epsilon
    },
  }
}

// Parallax effect
export function useParallax(
  speed: number = 0.5
) {
  const offset = ref(0)
  
  function handleScroll() {
    offset.value = window.scrollY * speed
  }
  
  onMounted(() => {
    window.addEventListener('scroll', handleScroll, { passive: true })
  })
  
  onUnmounted(() => {
    window.removeEventListener('scroll', handleScroll)
  })
  
  return {
    offset,
  }
}
