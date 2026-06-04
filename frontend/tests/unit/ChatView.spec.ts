import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import ChatView from '@/views/ChatView.vue'
import api from '@/api/client'

const pushMock = vi.fn()
const messageMock = { warning: vi.fn(), error: vi.fn(), success: vi.fn(), info: vi.fn() }

vi.mock('@/api/client', () => ({
  default: { post: vi.fn() },
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
}))

vi.mock('naive-ui', async () => {
  const actual = await vi.importActual<typeof import('naive-ui')>('naive-ui')
  const ButtonStub = defineComponent({
    emits: ['click'],
    setup(_, { slots, emit, attrs }) {
      return () => h('button', { ...attrs, onClick: () => emit('click') }, slots.default?.())
    },
  })
  const EmptyStub = defineComponent({
    props: ['description'],
    setup(props) {
      return () => h('div', props.description as string)
    },
  })
  const InputStub = defineComponent({
    props: ['value', 'modelValue', 'placeholder', 'disabled'],
    emits: ['update:value'],
    setup(props, { emit, attrs }) {
      return () =>
        h('textarea', {
          ...attrs,
          placeholder: props.placeholder,
          disabled: props.disabled,
          value: props.value ?? props.modelValue ?? '',
          onInput: (e: Event) => emit('update:value', (e.target as HTMLTextAreaElement).value),
        })
    },
  })
  return {
    ...actual,
    NButton: ButtonStub,
    NEmpty: EmptyStub,
    NInput: InputStub,
    useMessage: () => messageMock,
  }
})

describe('ChatView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('warns when submitting an empty query', async () => {
    const wrapper = mount(ChatView)
    await wrapper.get('button').trigger('click')
    expect(messageMock.warning).toHaveBeenCalled()
  })

  it('renders answer and sources after a successful query', async () => {
    vi.mocked(api.post).mockResolvedValueOnce({
      data: {
        answer: '这是回答',
        sources: [{ report_id: '7', content: '来源片段内容' }],
      },
    } as never)

    const wrapper = mount(ChatView)
    await wrapper.get('textarea').setValue('帮我总结一下')
    await wrapper.get('button').trigger('click')
    await nextTick()
    await nextTick()

    expect(api.post).toHaveBeenCalledWith('/api/v1/knowledge/query', expect.objectContaining({
      query: '帮我总结一下',
      top_k: 5,
      session_id: expect.any(String),
    }))
    expect(wrapper.text()).toContain('这是回答')
    expect(wrapper.text()).toContain('来源片段内容')
  })

  it('shows an error when the query request fails', async () => {
    vi.mocked(api.post).mockRejectedValueOnce(new Error('boom'))

    const wrapper = mount(ChatView)
    await wrapper.get('textarea').setValue('会失败吗')
    await wrapper.get('button').trigger('click')
    await nextTick()

    expect(messageMock.error).toHaveBeenCalled()
  })
})
