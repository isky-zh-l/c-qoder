<script setup lang="ts">
import { computed } from 'vue'
import { highlightC } from '../utils/cHighlight'

const props = defineProps<{
  source: string
  language?: 'c' | 'h' | 'text' | string | null
}>()

const highlighted = computed(() => highlightC(props.source))
</script>

<template>
  <pre
    class="code-view"
    :class="`language-${language || 'text'}`"
    :aria-label="`${language || 'text'} source`"
  ><code v-html="highlighted"></code></pre>
</template>

<style scoped>
.code-view {
  margin: 0;
  padding: 18px 19px 20px;
  overflow-x: auto;
  color: #d4d4d4;
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.75;
  tab-size: 2;
  white-space: pre;
}

.code-view code {
  font: inherit;
  white-space: inherit;
}

@media (max-width: 640px) {
  .code-view {
    padding: 14px 14px 16px;
    font-size: 11.5px;
  }
}
</style>
