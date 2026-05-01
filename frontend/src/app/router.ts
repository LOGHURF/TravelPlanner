import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '@/pages/HomePage.vue'
import PlanningPage from '@/pages/PlanningPage.vue'
import PlanResultPage from '@/pages/PlanResultPage.vue'


export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior() {
    return { top: 0, left: 0 }
  },
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomePage,
    },
    {
      path: '/planning',
      name: 'planning',
      component: PlanningPage,
    },
    {
      path: '/plan/:planId',
      name: 'plan-result',
      component: PlanResultPage,
      props: true,
    },

    {
      path: '/:pathMatch(.*)*',
      redirect: '/',
    },
  ],
})
