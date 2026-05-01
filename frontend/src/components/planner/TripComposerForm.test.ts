import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import TripComposerForm from '@/components/planner/TripComposerForm.vue'

describe('TripComposerForm', () => {
  it('emits submit when required fields are completed', async () => {
    const wrapper = mount(TripComposerForm)

    const form = wrapper.vm as unknown as { formState: { destination: string } }
    form.formState.destination = '北京'
    await wrapper.vm.$nextTick()

    await wrapper.find('form').trigger('submit.prevent')

    expect(wrapper.emitted('submit')).toBeTruthy()
    expect(wrapper.emitted('submit')?.[0]?.[0]).toMatchObject({
      destination: '北京',
    })
  })

  it('submits duration instead of the rejected days field', async () => {
    const wrapper = mount(TripComposerForm)

    const form = wrapper.vm as unknown as {
      formState: { destination: string; duration: number }
    }
    form.formState.destination = '北京'
    form.formState.duration = 5
    await wrapper.vm.$nextTick()

    await wrapper.find('form').trigger('submit.prevent')

    const payload = wrapper.emitted('submit')?.[0]?.[0] as Record<string, unknown>
    expect(payload.duration).toBe(5)
    expect(payload).not.toHaveProperty('days')
  })

  it('does not emit submit when destination is empty', async () => {
    const wrapper = mount(TripComposerForm)
    await wrapper.find('form').trigger('submit.prevent')
    expect(wrapper.emitted('submit')).toBeFalsy()
  })
})
