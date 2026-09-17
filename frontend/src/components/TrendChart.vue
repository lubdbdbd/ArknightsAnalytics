<script setup>
import { computed } from 'vue'
const props = defineProps({ rows: { type: Array, default: () => [] } })
const maximum = computed(() => Math.max(...props.rows.map(row => Number(row.paid_amount) || 0), 1))
const points = computed(() => props.rows.map((row, index) => (50 + index / Math.max(props.rows.length - 1, 1) * 840)+','+(200 - (Number(row.paid_amount) || 0) / maximum.value * 165)).join(' '))
</script>
<template>
<div class="trend-chart"><svg viewBox="0 0 920 240" role="img" aria-label="ERP模拟经营收入趋势">
<defs><linearGradient id="trend-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#158a72" stop-opacity=".22"/><stop offset="100%" stop-color="#158a72" stop-opacity=".015"/></linearGradient></defs>
<g v-for="tick in [0,1,2,3]" :key="tick"><line x1="50" x2="890" :y1="35+tick*55" :y2="35+tick*55" stroke="#e8ece8" stroke-dasharray="4 5"/><text x="0" :y="39+tick*55" fill="#81908b" font-size="11">{{ ((maximum*(3-tick)/3)/1000).toFixed(0) }}k</text></g>
<polygon v-if="rows.length" :points="'50,200 '+points+' 890,200'" fill="url(#trend-fill)"/>
<polyline :points="points" fill="none" stroke="#14816a" stroke-width="2.6" stroke-linejoin="round"/>
<text v-for="index in [0, Math.floor(rows.length/3), Math.floor(rows.length*2/3), rows.length-1]" :key="index" :x="50+index/Math.max(rows.length-1,1)*840" y="228" :text-anchor="index===rows.length-1?'end':'start'" fill="#81908b" font-size="11">{{ rows[index]?.date }}</text>
</svg></div>
</template>
