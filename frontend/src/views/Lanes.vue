<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'

interface Row {
  id: number
  slot_no: string
  sku_name: string
  capacity: number
  stock: number
  in_transit: number
  gap: number
  fill_qty: number
  status: 'need_fill' | 'full' | 'overbooked'
  reason: string
  fill_pct: number
}

const rows = ref<Row[]>([])
const refill = ref<any>(null)
const savingId = ref<number | null>(null)
const error = ref('')

const statusLabel: Record<string, string> = { need_fill: '待补', full: '满仓', overbooked: '超占' }

onMounted(async () => {
  rows.value = await api('/lanes')
  // 读最新补货单（无单时后端按现态建一张），不重复造单，小票即“最新单行状态”
  refill.value = await api('/refills/latest?location_id=1')
})

async function save(r: Row) {
  error.value = ''
  if (!Number.isInteger(r.stock) || r.stock < 0 || !Number.isInteger(r.in_transit) || r.in_transit < 0) {
    error.value = `${r.slot_no}：库存与在途必须为非负整数`
    return
  }
  savingId.value = r.id
  try {
    // 一次保存：后端在同一事务内提交货道数字并重算最新补货单，
    // 响应同时带回货道现态、最新单全部行与满仓/超占计数，四处口径同跳变
    const resp = await api(`/lanes/${r.id}`, {
      method: 'PATCH',
      body: JSON.stringify({ stock: r.stock, in_transit: r.in_transit }),
    })
    const idx = rows.value.findIndex((x) => x.id === r.id)
    if (idx >= 0) rows.value[idx] = resp.lane
    refill.value = { id: resp.order_id, location_id: resp.location_id, lines: resp.lines,
      total_fill: resp.total_fill, need_fill_count: resp.need_fill_count,
      full_count: resp.full_count, overbooked_count: resp.overbooked_count }
  } catch (e: any) {
    error.value = `${r.slot_no} 保存失败：${e.message || e}`
  } finally {
    savingId.value = null
  }
}
</script>

<template>
  <h1>货道格子</h1>
  <p class="sub">机面货道网格 · 改库存/在途后保存，货道现态、最新补货单行、满仓与汇总计数同跳变</p>
  <p v-if="error" class="vf-err">{{ error }}</p>
  <div class="vf-machine-layout">
    <div class="vf-slot-grid">
      <div v-for="r in rows" :key="r.id" class="vf-slot" :class="`vf-st-${r.status}`">
        <div class="vf-slot-no">
          {{ r.slot_no }}
          <span class="vf-badge" :class="`vf-badge-${r.status}`">{{ statusLabel[r.status] }}</span>
        </div>
        <div class="vf-slot-sku">{{ r.sku_name }}</div>
        <div class="vf-slot-bar">
          <div
            class="vf-slot-fill"
            :class="{ 'vf-need': r.status === 'need_fill', 'vf-over': r.status === 'overbooked' }"
            :style="{ width: Math.min(r.fill_pct, 100) + '%' }"
          />
        </div>
        <div class="vf-slot-meta">容量 {{ r.capacity }} · 库存+在途 {{ r.stock + r.in_transit }}</div>
        <div class="vf-edit">
          <label>库存
            <input type="number" min="0" step="1" v-model.number="r.stock" :disabled="savingId === r.id" />
          </label>
          <label>在途
            <input type="number" min="0" step="1" v-model.number="r.in_transit" :disabled="savingId === r.id" />
          </label>
          <button class="btn vf-save" :disabled="savingId === r.id" @click="save(r)">
            {{ savingId === r.id ? '保存中' : '保存' }}
          </button>
        </div>
        <p v-if="r.status === 'overbooked'" class="vf-reason vf-reason-over">{{ r.reason }}</p>
        <p v-else-if="r.status === 'full'" class="vf-reason vf-reason-full">{{ r.reason }}</p>
      </div>
    </div>
    <aside class="vf-receipt" v-if="refill">
      <h2>*** 最新补货单 #{{ refill.id }} ***</h2>
      <div class="vf-receipt-line" style="font-weight:700;border-bottom:2px dashed #8a7e64">
        <span>货道 / 商品</span><span>补量</span>
      </div>
      <div class="vf-receipt-line" v-for="l in refill.lines" :key="l.lane_id">
        <span>{{ l.slot_no }} {{ l.sku_name }}
          <small :class="`vf-badge-${l.status}`">（{{ statusLabel[l.status] }}）</small>
          <small v-if="l.status === 'overbooked'" class="vf-reason-over vf-reason-inline">{{ l.reason }}</small>
        </span>
        <span>{{ l.fill_qty }} / {{ l.gap < 0 ? `超 ${-l.gap}` : `缺 ${l.gap}` }}</span>
      </div>
      <p class="vf-counts">满仓 {{ refill.full_count }} · 超占 {{ refill.overbooked_count }} · 待补 {{ refill.need_fill_count }}</p>
      <p class="muted" style="margin:0.5rem 0 0;font-size:0.72rem;color:#6a5e48;text-align:center">
        — 保存后本小票与机面同时跳变 —
      </p>
    </aside>
  </div>
</template>
