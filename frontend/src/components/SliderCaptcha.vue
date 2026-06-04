<template>
  <div class="select-none" :class="{ 'pointer-events-none opacity-70': verified }">
    <div
      ref="trackRef"
      data-test="slider-track"
      class="relative h-12 w-full overflow-hidden rounded-xl border transition-colors"
      :class="trackClass"
      @mousedown="onStart"
      @touchstart.prevent="onStart"
    >
      <!-- 已滑过区域 -->
      <div
        class="absolute inset-y-0 left-0 rounded-l-xl transition-all duration-75"
        :class="fillClass"
        :style="{ width: handleX + 24 + 'px' }"
      />

      <!-- 提示文字 -->
      <span
        v-if="!verified"
        class="pointer-events-none absolute inset-0 flex items-center justify-center text-sm font-medium select-none"
        :class="dragging ? 'text-transparent' : 'text-[#a99b89]'"
      >
        → {{ copy.slideToVerify }}
      </span>

      <!-- 成功图标 -->
      <span
        v-if="verified"
        class="pointer-events-none absolute inset-0 flex items-center justify-center text-sm font-semibold text-white"
      >
        ✓ {{ copy.verified }}
      </span>

      <!-- 拖拽滑块 -->
      <div
        data-test="slider-handle"
        class="absolute inset-y-0 flex w-12 cursor-grab items-center justify-center rounded-xl bg-white shadow-md transition-all duration-75 active:cursor-grabbing"
        :class="handleClass"
        :style="{ left: handleX + 'px' }"
      >
        <span class="text-lg" :class="verified ? 'text-emerald-500' : 'text-[#8e8172]'">
          {{ verified ? '✓' : '⇌' }}
        </span>
      </div>
    </div>

    <p v-if="failed" class="mt-1.5 text-xs text-red-400">{{ copy.retryHint }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { useLocaleStore } from '@/stores/locale'

const emit = defineEmits<{
  (e: 'verify', x: number): void
}>()

const locale = useLocaleStore()
const trackRef = ref<HTMLDivElement>()
const handleX = ref(0)
const dragging = ref(false)
const verified = ref(false)
const failed = ref(false)

const copy = computed(() =>
  locale.isChinese
    ? { slideToVerify: '向右滑动完成验证', verified: '验证通过', retryHint: '验证失败，请重试' }
    : { slideToVerify: 'Slide to verify', verified: 'Verified', retryHint: 'Verification failed, please retry' },
)

const trackClass = computed(() => {
  if (verified.value) return 'border-emerald-200 bg-emerald-50'
  if (failed.value) return 'border-red-200 bg-red-50'
  return 'border-[#e2d8ca] bg-[#f9f5ee]'
})

const fillClass = computed(() => {
  if (verified.value) return 'bg-emerald-400'
  if (failed.value) return 'bg-red-300'
  return 'bg-gradient-to-r from-[#c8d9eb] to-[#8db3d9]'
})

const handleClass = computed(() => {
  if (verified.value) return 'border border-emerald-200'
  if (failed.value) return 'border border-red-200'
  return 'border border-[#ddd3c5]'
})

let maxX = 0

function clamp(v: number) {
  return Math.max(0, Math.min(v, maxX))
}

function getClientX(e: MouseEvent | TouchEvent): number {
  return e instanceof MouseEvent ? e.clientX : e.touches[0].clientX
}

function onStart(e: MouseEvent | TouchEvent) {
  if (verified.value) return
  dragging.value = true
  failed.value = false
  if (trackRef.value) {
    maxX = trackRef.value.offsetWidth - 50
  }
  const startX = getClientX(e) - handleX.value
  document.body.style.userSelect = 'none'

  const onMove = (ev: MouseEvent | TouchEvent) => {
    if (!dragging.value) return
    handleX.value = clamp(getClientX(ev) - startX)
  }
  const onEnd = () => {
    dragging.value = false
    document.body.style.userSelect = ''
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', onEnd)
    document.removeEventListener('touchmove', onMove)
    document.removeEventListener('touchend', onEnd)

    if (handleX.value >= maxX * 0.9) {
      handleX.value = maxX
      verified.value = true
      emit('verify', maxX)
    } else {
      handleX.value = 0
    }
  }

  document.addEventListener('mousemove', onMove)
  document.addEventListener('mouseup', onEnd)
  document.addEventListener('touchmove', onMove)
  document.addEventListener('touchend', onEnd)
}

function reset() {
  handleX.value = 0
  verified.value = false
  failed.value = false
}

function markFailed() {
  verified.value = false
  failed.value = true
  setTimeout(() => {
    failed.value = false
    handleX.value = 0
  }, 1200)
}

onBeforeUnmount(() => {
  document.body.style.userSelect = ''
})

defineExpose({ reset, markFailed })
</script>
