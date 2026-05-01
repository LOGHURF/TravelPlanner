<script setup lang="ts">
/**
 * Design Tokens Showcase
 * 
 * This component demonstrates the new Apple-inspired design system.
 * It serves as a visual test and documentation for the design tokens.
 */

import { ref } from 'vue'
import { 
  Button, 
  Card, 
  Input, 
  Pill, 
  Progress, 
  Skeleton,
  Toast 
} from '@/components/ui'

const colors = [
  { name: 'Primary', var: '--color-primary', class: 'bg-brand' },
  { name: 'Success', var: '--color-success', class: 'bg-success' },
  { name: 'Warning', var: '--color-warning', class: 'bg-warning' },
  { name: 'Error', var: '--color-error', class: 'bg-error' },
  { name: 'Info', var: '--color-info', class: 'bg-info' },
]

const grays = [
  { name: 'BG Primary', var: '--color-bg-primary', class: 'bg-primary' },
  { name: 'BG Secondary', var: '--color-bg-secondary', class: 'bg-secondary' },
  { name: 'BG Tertiary', var: '--color-bg-tertiary', class: 'bg-tertiary' },
]

const shadows = [
  { name: 'Small', var: '--shadow-sm', class: 'shadow-sm' },
  { name: 'Medium', var: '--shadow-md', class: 'shadow-md' },
  { name: 'Large', var: '--shadow-lg', class: 'shadow-lg' },
]

// Component test states
const inputValue = ref('')
const inputError = ref('')
const selectedPill = ref('option1')
const progressValue = ref(68)
const toastVisible = ref(false)
const toastType = ref<'success' | 'error' | 'warning' | 'info'>('success')

const pillOptions = [
  { label: '选项 1', value: 'option1' },
  { label: '选项 2', value: 'option2' },
  { label: '选项 3', value: 'option3' },
]

function showToast(type: 'success' | 'error' | 'warning' | 'info') {
  toastType.value = type
  toastVisible.value = true
}

function validateInput() {
  if (!inputValue.value) {
    inputError.value = '请输入内容'
  } else {
    inputError.value = ''
  }
}
</script>

<template>
  <div class="showcase">
    <header class="showcase-header">
      <h1 class="text-4xl font-bold">Design System Test</h1>
      <p class="text-secondary mt-2">Phase 1 & 2: Tokens & Components</p>
    </header>
    
    <!-- Colors -->
    <section class="showcase-section">
      <h2 class="text-2xl font-semibold mb-4">Brand Colors</h2>
      <div class="flex gap-4 flex-wrap">
        <div
          v-for="color in colors"
          :key="color.name"
          class="color-box"
          :class="color.class"
        >
          <span class="text-inverse font-medium">{{ color.name }}</span>
          <code class="text-xs text-inverse opacity-80">{{ color.var }}</code>
        </div>
      </div>
    </section>

    <!-- Grays -->
    <section class="showcase-section">
      <h2 class="text-2xl font-semibold mb-4">Background Colors</h2>
      <div class="flex gap-4 flex-wrap">
        <div
          v-for="gray in grays"
          :key="gray.name"
          class="color-box border"
          :class="gray.class"
        >
          <span class="font-medium">{{ gray.name }}</span>
          <code class="text-xs text-secondary">{{ gray.var }}</code>
        </div>
      </div>
    </section>

    <!-- Shadows -->
    <section class="showcase-section">
      <h2 class="text-2xl font-semibold mb-4">Shadows</h2>
      <div class="flex gap-6 flex-wrap">
        <div
          v-for="shadow in shadows"
          :key="shadow.name"
          class="shadow-box bg-primary"
          :class="shadow.class"
        >
          <span class="font-medium">{{ shadow.name }}</span>
          <code class="text-xs text-secondary">{{ shadow.var }}</code>
        </div>
      </div>
    </section>

    <!-- Typography -->
    <section class="showcase-section">
      <h2 class="text-2xl font-semibold mb-4">Typography</h2>
      <Card padding="lg">
        <div class="space-y-2">
          <p class="text-5xl font-bold">Heading 5XL</p>
          <p class="text-4xl font-bold">Heading 4XL</p>
          <p class="text-3xl font-semibold">Heading 3XL</p>
          <p class="text-2xl font-semibold">Heading 2XL</p>
          <p class="text-xl font-medium">Heading XL</p>
          <p class="text-lg font-medium">Heading LG</p>
          <p class="text-base">Body Text</p>
          <p class="text-sm text-secondary">Small Text</p>
          <p class="text-xs text-tertiary">Extra Small</p>
        </div>
      </Card>
    </section>

    <!-- Buttons -->
    <section class="showcase-section">
      <h2 class="text-2xl font-semibold mb-4">Buttons</h2>
      <Card padding="lg">
        <div class="space-y-6">
          <div class="flex gap-4 flex-wrap items-center">
            <Button variant="primary">Primary</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="danger">Danger</Button>
          </div>
          
          <div class="flex gap-4 flex-wrap items-center">
            <Button size="sm">Small</Button>
            <Button size="md">Medium</Button>
            <Button size="lg">Large</Button>
          </div>
          
          <div class="flex gap-4 flex-wrap items-center">
            <Button :loading="true">Loading</Button>
            <Button disabled>Disabled</Button>
            <Button variant="primary" block>Block Button</Button>
          </div>
        </div>
      </Card>
    </section>

    <!-- Cards -->
    <section class="showcase-section">
      <h2 class="text-2xl font-semibold mb-4">Cards</h2>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card variant="default" hoverable>
          <template #header>Default Card</template>
          <p class="text-secondary">With hover effect</p>
        </Card>
        
        <Card variant="outlined">
          <template #header>Outlined Card</template>
          <p class="text-secondary">Clean borders</p>
        </Card>
        
        <Card variant="elevated" hoverable clickable>
          <template #header>Elevated Card</template>
          <p class="text-secondary">Clickable with shadow</p>
        </Card>
      </div>
    </section>

    <!-- Inputs -->
    <section class="showcase-section">
      <h2 class="text-2xl font-semibold mb-4">Inputs</h2>
      <Card padding="lg">
        <div class="space-y-4 max-w-md">
          <Input
            v-model="inputValue"
            label="用户名"
            placeholder="请输入用户名"
            :error="inputError"
            @blur="validateInput"
          />
          
          <Input
            label="邮箱"
            type="email"
            placeholder="example@email.com"
          >
            <template #hint>请输入有效的邮箱地址</template>
          </Input>
          
          <Input
            label="密码"
            type="password"
            placeholder="••••••••"
            required
          />
          
          <div class="flex gap-4">
            <Input size="sm" placeholder="Small input" />
            <Input size="md" placeholder="Medium input" />
            <Input size="lg" placeholder="Large input" />
          </div>
        </div>
      </Card>
    </section>

    <!-- Pills -->
    <section class="showcase-section">
      <h2 class="text-2xl font-semibold mb-4">Pills</h2>
      <Card padding="lg">
        <div class="space-y-4">
          <div>
            <p class="text-sm text-secondary mb-2">单选</p>
            <Pill v-model="selectedPill" :options="pillOptions" />
          </div>
          
          <div>
            <p class="text-sm text-secondary mb-2">尺寸</p>
            <div class="flex gap-4 items-center">
              <Pill size="sm" :options="[{label: 'Small', value: 'sm'}]" />
              <Pill size="md" :options="[{label: 'Medium', value: 'md'}]" />
              <Pill size="lg" :options="[{label: 'Large', value: 'lg'}]" />
            </div>
          </div>
        </div>
      </Card>
    </section>

    <!-- Progress -->
    <section class="showcase-section">
      <h2 class="text-2xl font-semibold mb-4">Progress</h2>
      <Card padding="lg">
        <div class="space-y-6">
          <div>
            <p class="text-sm text-secondary mb-2">Linear</p>
            <Progress v-model="progressValue" />
            <div class="flex gap-2 mt-2">
              <Button size="sm" @click="progressValue = Math.max(0, progressValue - 10)">-10</Button>
              <Button size="sm" @click="progressValue = Math.min(100, progressValue + 10)">+10</Button>
            </div>
          </div>
          
          <div class="flex items-center gap-8">
            <div>
              <p class="text-sm text-secondary mb-2">Circular</p>
              <Progress v-model="progressValue" variant="circular" :size="100" />
            </div>
            
            <div>
              <p class="text-sm text-secondary mb-2">Indeterminate</p>
              <Progress :indeterminate="true" />
            </div>
          </div>
        </div>
      </Card>
    </section>

    <!-- Skeleton -->
    <section class="showcase-section">
      <h2 class="text-2xl font-semibold mb-4">Skeleton</h2>
      <Card padding="lg">
        <div class="space-y-4 max-w-md">
          <div class="flex gap-4 items-center">
            <Skeleton circle :size="48" />
            <div class="flex-1">
              <Skeleton text :lines="2" />
            </div>
          </div>
          
          <Skeleton width="100%" height="120px" radius="var(--radius-lg)" />
          
          <div class="flex gap-2">
            <Skeleton width="80px" height="32px" radius="var(--radius-full)" />
            <Skeleton width="80px" height="32px" radius="var(--radius-full)" />
            <Skeleton width="80px" height="32px" radius="var(--radius-full)" />
          </div>
        </div>
      </Card>
    </section>

    <!-- Toast -->
    <section class="showcase-section">
      <h2 class="text-2xl font-semibold mb-4">Toast</h2>
      <Card padding="lg">
        <div class="flex gap-4 flex-wrap">
          <Button @click="showToast('success')">Success Toast</Button>
          <Button variant="danger" @click="showToast('error')">Error Toast</Button>
          <Button variant="secondary" @click="showToast('warning')">Warning Toast</Button>
          <Button variant="ghost" @click="showToast('info')">Info Toast</Button>
        </div>
      </Card>
    </section>

    <!-- Status -->
    <section class="showcase-section">
      <Card padding="lg" class="bg-success-soft border-success">
        <div class="flex items-center gap-3">
          <span class="text-success text-2xl">✓</span>
          <div>
            <p class="font-semibold text-success">Phase 1 & 2 Complete!</p>
            <p class="text-sm text-secondary">Design tokens and UI components are ready</p>
          </div>
        </div>
      </Card>
    </section>

    <!-- Toast Container -->
    <Toast
      v-model:visible="toastVisible"
      :type="toastType"
      :message="`This is a ${toastType} message!`"
      position="top-right"
    />
  </div>
</template>

<style scoped>
.showcase {
  min-height: 100vh;
  background: var(--color-bg-secondary);
  padding: var(--space-8);
}

.showcase-header {
  text-align: center;
  margin-bottom: var(--space-12);
  padding: var(--space-8) 0;
}

.showcase-section {
  margin-bottom: var(--space-10);
}

.color-box {
  width: 140px;
  height: 100px;
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
}

.shadow-box {
  width: 120px;
  height: 80px;
  border-radius: var(--radius-md);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
}

@media (max-width: 768px) {
  .showcase {
    padding: var(--space-4);
  }
  
  .color-box {
    width: 100px;
    height: 80px;
  }
}
</style>
