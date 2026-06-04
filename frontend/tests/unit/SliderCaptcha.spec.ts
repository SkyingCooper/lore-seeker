import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import SliderCaptcha from '@/components/SliderCaptcha.vue'
import { useLocaleStore } from '@/stores/locale'

describe('SliderCaptcha', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders locale-aware prompt text', async () => {
    const locale = useLocaleStore()
    const wrapper = mount(SliderCaptcha)

    expect(wrapper.text()).toContain('向右滑动完成验证')

    locale.setLocale('en-US')
    await nextTick()
    expect(wrapper.text()).toContain('Slide to verify')
  })

  it('emits verify when dragged near the end of the track', async () => {
    const wrapper = mount(SliderCaptcha, {
      attachTo: document.body,
    })

    const track = wrapper.get('[data-test="slider-track"]')
    Object.defineProperty(track.element, 'offsetWidth', { configurable: true, value: 200 })

    await track.trigger('mousedown', { clientX: 0 })
    document.dispatchEvent(new MouseEvent('mousemove', { clientX: 200 }))
    document.dispatchEvent(new MouseEvent('mouseup'))
    await nextTick()

    expect(wrapper.emitted('verify')).toBeTruthy()
    expect(wrapper.text()).toContain('验证通过')
  })

  it('supports failure and reset flows through exposed methods', async () => {
    vi.useFakeTimers()
    const wrapper = mount(SliderCaptcha)

    ;(wrapper.vm as unknown as { markFailed: () => void; reset: () => void }).markFailed()
    await nextTick()
    expect(wrapper.text()).toContain('验证失败，请重试')

    vi.advanceTimersByTime(1300)
    await nextTick()
    expect(wrapper.text()).not.toContain('验证失败，请重试')

    ;(wrapper.vm as unknown as { reset: () => void }).reset()
    await nextTick()
    expect(wrapper.text()).toContain('向右滑动完成验证')
    vi.useRealTimers()
  })
})
