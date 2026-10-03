<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../api'

const rows = ref<any[]>([])
const refill = ref<any>(null)
const saving = ref(false)
const savedMsg = ref('')

// 已落库的快照，用于判断哪些行被改过
const snapshot = ref<Record<number, { stock: number; in_transit: number }>>({})

const dirtyIds = computed(() =>
  rows.value
    .filter(r => snapshot.value[r.id] &&
      (snapshot.value[r.id].stock !== Number(r.stock) ||
       snapshot.value[r.id].in_transit !== Number(r.in_transit)))
    .map(r => r.id),
)

// 互斥口径：超占与满仓绝不并句。超占只由 库存+在途 > 容量 单独表达。
function kind(r: any): 'overbooked' | 'full' | 'need' {
  if (Number(r.gap) < 0) return 'overbooked'
  if (Number(r.gap) === 0) return 'full'
  return 'need'
}
const kindText = { overbooked: '超占', full: '满仓', need: '待补' } as const

function rememberSnapshot() {
  snapshot.value = Object.fromEntries(
    rows.value.map(r => [r.id, { stock: Number(r.stock), in_transit: Number(r.in_transit) }]),
  )
}

async function refresh() {
  rows.value = await api('/lanes?location_id=1')
  refill.value = await api('/refills/latest?location_id=1')
  rememberSnapshot()
}

async function save() {
  saving.value = true
  savedMsg.value = ''
  try {
    const lanes = dirtyIds.value.map(id => {
      const r = rows.value.find(x => x.id === id)
      return { id, stock: Number(r.stock), in_transit: Number(r.in_transit) }
    })
    // 一次保存：货道数字、最新补货单行状态、满仓名单、汇总计数同事务跳变。
    const order = await api('/lanes?location_id=1', {
      method: 'PUT',
      body: JSON.stringify({ location_id: 1, lanes }),
    })
    rows.value = await api('/lanes?location_id=1')
    refill.value = order
    rememberSnapshot()
    savedMsg.value = '已保存：货道现态、最新补货单、满仓名单与汇总已同步'
  } catch (e: any) {
    savedMsg.value = '保存失败：' + (e?.message || e)
  } finally {
    saving.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <h1>货道格子</h1>
  <p class="sub">机面货道网格 · 改库存/在途后保存，右侧补货小票同一跳变</p>
  <div class="vf-edit-bar">
    <button class="btn" :disabled="saving || dirtyIds.length === 0" @click="save">
      {{ saving ? '保存中…' : `保存改动${dirtyIds.length ? `（${dirtyIds.length} 行）` : ''}` }}
    </button>
    <span v-if="savedMsg" class="vf-saved-note">{{ savedMsg }}</span>
  </div>
  <div class="vf-machine-layout">
    <div class="vf-slot-grid">
      <div v-for="r in rows" :key="r.id" class="vf-slot" :class="`vf-slot-${kind(r)}`">
        <div class="vf-slot-no">{{ r.slot_no }}</div>
        <div class="vf-slot-sku">{{ r.sku_name }}</div>
        <span class="badge" :class="`badge-${kind(r) === 'overbooked' ? 'bad' : kind(r) === 'full' ? 'ok' : 'warn'}`">
          {{ kindText[kind(r)] }}
        </span>
        <div class="vf-slot-bar">
          <div
            class="vf-slot-fill"
            :class="{ 'vf-need': kind(r) === 'need', 'vf-over': kind(r) === 'overbooked' }"
            :style="{ width: Math.min(Number(r.fill_pct), 100) + '%' }"
          />
        </div>
        <!-- 三种口径各说各话：超占原因单独成句，绝不与满仓并句 -->
        <div v-if="kind(r) === 'overbooked'" class="vf-slot-meta vf-meta-over">
          超占：{{ r.stock }}＋{{ r.in_transit }} ＞ {{ r.capacity }}
        </div>
        <div v-else-if="kind(r) === 'full'" class="vf-slot-meta">满仓：{{ r.stock }}＋{{ r.in_transit }} ＝ {{ r.capacity }}</div>
        <div v-else class="vf-slot-meta">{{ r.stock }}/{{ r.capacity }} · 缺 {{ r.gap }}</div>
        <div class="vf-slot-edit">
          <label>库<input v-model.number="r.stock" type="number" min="0" /></label>
          <label>途<input v-model.number="r.in_transit" type="number" min="0" /></label>
        </div>
      </div>
    </div>
    <aside class="vf-receipt" v-if="refill">
      <h2>*** 补货建议单 ***</h2>
      <div class="vf-receipt-line" v-for="l in refill.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }}
          <small :class="`vf-line-${l.status}`">{{ l.status === 'need_fill' ? '待补' : l.status === 'full' ? '满仓' : '超占' }}</small>
        </span>
        <span>x{{ l.fill_qty }}</span>
      </div>
      <p class="muted" style="margin:0.75rem 0 0;font-size:0.72rem;color:#6a5e48;text-align:center">
        超占 {{ refill.overbooked_count }} · 满仓 {{ refill.full_count }} · 待补 {{ refill.need_fill_count }}
      </p>
    </aside>
  </div>
</template>

<style scoped>
.vf-edit-bar { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem; }
.vf-saved-note { font-size: 0.75rem; color: var(--vf-led); }
.vf-slot .badge { margin-top: 0.25rem; align-self: flex-start; font-size: 0.6rem; padding: 0.05rem 0.35rem; }
.vf-slot-over { border-color: var(--vf-red); box-shadow: inset 0 0 12px rgba(255,92,108,0.18); }
.vf-slot-full { border-color: rgba(57,255,136,0.55); }
.vf-slot-fill.vf-over { background: var(--vf-red); }
.vf-meta-over { color: var(--vf-red); font-weight: 700; }
.vf-slot-edit { display: flex; gap: 0.3rem; margin-top: 0.25rem; }
.vf-slot-edit label { font-size: 0.58rem; color: var(--vf-dim); display: flex; align-items: center; gap: 0.15rem; }
.vf-slot-edit input {
  width: 2.6rem; font-size: 0.66rem; padding: 0.1rem 0.2rem;
  background: #0a0e14; color: var(--vf-text); border: 1px solid #3a4656; border-radius: 3px;
}
.vf-line-overbooked { color: var(--vf-red); font-weight: 700; }
.vf-line-full { color: var(--vf-led); }
</style>
