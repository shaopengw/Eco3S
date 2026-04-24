<template>
  <div class="map-area">
    <div ref="mapContainer" class="map-canvas"></div>
    <div v-if="!hasDataToDisplay" class="map-empty">
      <div class="map-empty-icon">🗺️</div>
      <div class="map-empty-title">{{ t('simulationRunner.noMapData') || '暂无轨迹数据' }}</div>
      <div class="map-empty-sub">{{ t('simulationRunner.runToGenerate') || '请先运行模拟生成数据' }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount, computed, inject } from 'vue'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const useI18nFunc = inject('useI18n')
const { t } = useI18nFunc()

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  townsData: { type: Object, default: null },
  theme: { type: String, default: 'base' }
})

const emit = defineEmits(['node-click'])

const mapContainer = ref(null)
let map = null
let markerDict = {} // resident_id -> marker instance
let townsLayerGroup = null // layer group for towns and canals
let isFirstRender = true

const hasDataToDisplay = computed(() => {
  return hasGeoNodes.value || (props.townsData && (props.townsData.canals || props.townsData.other_towns));
})

const THEME = {
  childcare:     { fill: '#10b981', border: '#059669', bg: 'rgba(16,185,129,0.12)',  text: '#059669' },
  dining:        { fill: '#f59e0b', border: '#d97706', bg: 'rgba(245,158,11,0.12)',  text: '#d97706' },
  education:     { fill: '#6366f1', border: '#4f46e5', bg: 'rgba(99,102,241,0.12)', text: '#4f46e5' },
  eldercare:     { fill: '#8b5cf6', border: '#7c3aed', bg: 'rgba(139,92,246,0.12)', text: '#7c3aed' },
  entertainment: { fill: '#ec4899', border: '#be185d', bg: 'rgba(236,72,153,0.12)', text: '#be185d' },
  mental_health: { fill: '#14b8a6', border: '#0d9488', bg: 'rgba(20,184,166,0.12)', text: '#0d9488' },
  sport:         { fill: '#3b82f6', border: '#2563eb', bg: 'rgba(59,130,246,0.12)', text: '#2563eb' },
  travel:        { fill: '#06b6d4', border: '#0891b2', bg: 'rgba(6,182,212,0.12)',   text: '#0891b2' },
  base:          { fill: '#94a3b8', border: '#64748b', bg: 'rgba(148,163,184,0.12)', text: '#64748b' },
}

const JOB_THEME = {
  '农民':    { fill: '#22c55e', text: '#166534' },
  '工人':    { fill: '#64748b', text: '#334155' },
  '商人':    { fill: '#f59e0b', text: '#92400e' },
  '叛军':    { fill: '#ef4444', text: '#991b1b' },
  '无业':    { fill: '#a1a1aa', text: '#52525b' },
  'default': { fill: '#94a3b8', text: '#64748b' }
}

function tc(theme) {
  return THEME[theme] || THEME.base
}

function tj(job) {
  return JOB_THEME[job] || JOB_THEME['default']
}

const hasGeoNodes = computed(() => props.nodes.some(n => n.location_detail && Number.isFinite(n.location_detail.latitude) && Number.isFinite(n.location_detail.longitude)))

function makePopupContent(node) {
  const rows = []

  if (node.resident_id) {
    rows.push(`<div class="popup-row"><span class="popup-label">ID:</span><span class="popup-value">${node.resident_id}</span></div>`)
  }
  if (node.town) {
    rows.push(`<div class="popup-row"><span class="popup-label">${t('simulationRunner.town')}:</span><span class="popup-value">${node.town}</span></div>`)
  }
  if (node.job) {
    const jobColor = tj(node.job)
    rows.push(`<div class="popup-row"><span class="popup-label">${t('simulationRunner.job')}:</span><span class="popup-value" style="color:${jobColor.text}">${node.job}</span></div>`)
  }
  if (node.employed !== null && node.employed !== undefined) {
    rows.push(`<div class="popup-row"><span class="popup-label">${t('simulationRunner.employmentStatus')}:</span><span class="popup-value">${node.employed ? t('common.yes', '是') : t('common.no', '否')}</span></div>`)
  }
  if (node.income !== null && node.income !== undefined) {
    rows.push(`<div class="popup-row"><span class="popup-label">${t('simulationRunner.income')}:</span><span class="popup-value">${node.income}</span></div>`)
  }
  if (node.satisfaction !== null && node.satisfaction !== undefined) {
    const sat = parseFloat(node.satisfaction)
    const satColor = sat > 70 ? '#22c55e' : sat > 40 ? '#f59e0b' : '#ef4444'
    rows.push(`<div class="popup-row"><span class="popup-label">${t('simulationRunner.satisfaction')}:</span><span class="popup-value" style="color:${satColor}">${sat.toFixed(1)}%</span></div>`)
  }
  if (node.health_index !== null && node.health_index !== undefined) {
    rows.push(`<div class="popup-row"><span class="popup-label">${t('simulationRunner.healthIndex')}:</span><span class="popup-value">${node.health_index}</span></div>`)
  }

  const color = tc(props.theme)
  return `
    <div class="node-popup-header" style="background:${color.bg};color:${color.text};">
      <span class="popup-title">${t('simulationRunner.residentArchive').replace('#{id}', '')}</span>
    </div>
    <div class="popup-content">
      ${rows.length ? rows.join('') : `<div class="popup-empty">${t('simulationRunner.noData', '暂无详细信息')}</div>`}
    </div>
  `
}

function makeIcon(index, node, color, active = false) {
  const size = active ? 16 : 10
  const jobInfo = tj(node.job || 'default')
  const bg = active ? color.fill : jobInfo.fill
  const ring = active
    ? `0 0 0 3px ${color.fill}55, 0 4px 14px rgba(0,0,0,0.25)`
    : '0 2px 6px rgba(0,0,0,0.15)'

  return L.divIcon({
    className: '',
    html: `<div class="resident-dot" style="
      width:${size}px;height:${size}px;
      background:${bg};
      border: 1.5px solid #ffffff;
      box-shadow:${ring};
    "></div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  })
}

function renderTowns() {
  if (!map || !props.townsData) return
  
  if (townsLayerGroup) {
    map.removeLayer(townsLayerGroup)
  }
  
  townsLayerGroup = L.layerGroup().addTo(map)
  const bounds = []

  // 渲染运河与运河沿岸城镇
  if (props.townsData.canals) {
    props.townsData.canals.forEach(canal => {
      const latlngs = []
      canal.towns.forEach(town => {
        const latlng = [town.latitude, town.longitude]
        latlngs.push(latlng)
        bounds.push(latlng)
        
        L.circleMarker(latlng, {
          radius: 8,
          fillColor: '#3b82f6',
          color: '#ffffff',
          weight: 2,
          opacity: 1,
          fillOpacity: 0.9,
          interactive: false // 不能点击
        })
        .bindTooltip(town.name, { permanent: true, direction: 'right', className: 'town-label-transparent', offset: [8, 0], interactive: false })
        .addTo(townsLayerGroup)
      })
      
      // 运河连线
      L.polyline(latlngs, {
        color: '#60a5fa',
        weight: 3,
        opacity: 0.6,
        dashArray: '5, 10',
        lineJoin: 'round'
      }).addTo(townsLayerGroup)
    })
  }

  // 渲染其他城镇
  if (props.townsData.other_towns) {
    props.townsData.other_towns.forEach(town => {
      const latlng = [town.latitude, town.longitude]
      bounds.push(latlng)
      
      L.circleMarker(latlng, {
        radius: 6,
        fillColor: '#9ca3af',
        color: '#ffffff',
        weight: 1.5,
        opacity: 1,
        fillOpacity: 0.9,
        interactive: false // 不能点击
      })
      .bindTooltip(town.name, { permanent: true, direction: 'right', className: 'town-label-transparent', offset: [6, 0], interactive: false })
      .addTo(townsLayerGroup)
    })
  }

  // 渲染地图边界（可选，这里只用来调整视野）
  if (isFirstRender && bounds.length > 0 && props.nodes.length === 0) {
    map.fitBounds(L.latLngBounds(bounds), { padding: [40, 40], animate: true })
    isFirstRender = false
  }
}

function renderMap() {
  if (!map) return

  const geoNodes = props.nodes.filter(n => n.location_detail && Number.isFinite(n.location_detail.latitude) && Number.isFinite(n.location_detail.longitude))
  
  const currentIds = new Set()
  const color = tc(props.theme)
  const latlngs = []

  geoNodes.forEach((node, idx) => {
    const id = node.resident_id || idx
    currentIds.add(id)
    
    const latlng = [node.location_detail.latitude, node.location_detail.longitude]
    latlngs.push(latlng)

    if (markerDict[id]) {
      // 更新现有标记的位置和内容（使用动画平滑移动）
      const oldLatLng = markerDict[id].getLatLng()
      if (oldLatLng.lat !== latlng[0] || oldLatLng.lng !== latlng[1]) {
        // 如果位置发生变化，添加一个平滑移动的 CSS 类
        const iconElement = markerDict[id].getElement()
        if (iconElement) {
          iconElement.style.transition = 'all 1.5s ease-in-out'
        }
        markerDict[id].setLatLng(latlng)
      }
      markerDict[id].setIcon(makeIcon(idx, node, color))
      markerDict[id].getPopup().setContent(makePopupContent(node))
    } else {
      // 创建新标记
      const marker = L.marker(latlng, {
        icon: makeIcon(idx, node, color),
        zIndexOffset: idx * 100
      })

      const popupContent = makePopupContent(node)
      marker.bindPopup(popupContent, {
        autoClose: true,
        closeOnClick: false,
        className: 'resident-popup',
        maxWidth: 260,
        offset: [0, -8]
      })

      marker.on('click', () => {
        emit('node-click', node)
      })

      marker.addTo(map)
      markerDict[id] = marker
    }
  })

  // 移除不再存在的标记
  Object.keys(markerDict).forEach(id => {
    if (!currentIds.has(id) && !currentIds.has(Number(id))) {
      map.removeLayer(markerDict[id])
      delete markerDict[id]
    }
  })

  // 仅在首次渲染时自动缩放地图以适应所有点
  if (isFirstRender && latlngs.length > 0) {
    if (latlngs.length === 1) {
      map.setView(latlngs[0], 12)
    } else {
      map.fitBounds(L.latLngBounds(latlngs), { padding: [60, 60], animate: true })
    }
    isFirstRender = false
  }
}

let resizeObserver = null

onMounted(() => {
  map = L.map(mapContainer.value, { zoomControl: false }).setView([39.9, 116.4], 10)
  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager_nolabels/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; <a href="https://carto.com/">CARTO</a>',
    subdomains: 'abcd',
    maxZoom: 19
  }).addTo(map)
  renderTowns()
  renderMap()

  // 监听容器大小变化，防止 Leaflet 加载不全导致白边/灰边
  if (window.ResizeObserver && mapContainer.value) {
    resizeObserver = new ResizeObserver(() => {
      if (map) {
        map.invalidateSize()
      }
    })
    resizeObserver.observe(mapContainer.value)
  }
})

watch(() => props.townsData, renderTowns, { deep: true, immediate: true })
watch(() => [props.nodes, props.theme], renderMap, { deep: true })

onBeforeUnmount(() => {
  if (resizeObserver && mapContainer.value) {
    resizeObserver.unobserve(mapContainer.value)
    resizeObserver.disconnect()
  }
  if (map) map.remove()
})

function highlightResident(residentId) {
  if (!map || !markerDict[residentId]) return

  const marker = markerDict[residentId]
  const latlng = marker.getLatLng()

  // 1. 将地图平滑移动并缩放到该居民位置
  map.flyTo(latlng, 14, {
    animate: true,
    duration: 1.5
  })

  // 2. 打开弹窗
  setTimeout(() => {
    marker.openPopup()
  }, 1500)

  // 3. 可以在这里触发一下 node-click 事件，让外层更新状态
  const node = props.nodes.find(n => n.resident_id === residentId || n.resident_id === Number(residentId))
  if (node) {
    emit('node-click', node)
  }
}

defineExpose({ map, highlightResident })
</script>

<style scoped>
.map-area {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 400px;
}
.map-canvas {
  position: absolute;
  inset: 0;
  z-index: 1;
  background-color: #eef2f5; /* 配合浅蓝色水域的底色 */
}

/* 使大地部分变成浅灰色，水域保留较深的蓝色调 */
:deep(.leaflet-tile-pane) {
  filter: grayscale(0.1) contrast(1.1) brightness(1);
}
.map-empty {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  background: var(--bg, #f8fafc);
  pointer-events: none;
}
.map-empty-icon  { font-size: 40px; opacity: 0.25; }
.map-empty-title { font-size: 15px; font-weight: 600; color: #888888; }
.map-empty-sub   { font-size: 12px; color: #bbb; }
</style>

<style>
.resident-popup .leaflet-popup-content-wrapper {
  border-radius: 8px;
  padding: 0;
  overflow: hidden;
}
.resident-popup .leaflet-popup-content {
  margin: 0;
  min-width: 200px;
}
.node-popup-header {
  padding: 10px 14px;
  font-weight: 600;
  font-size: 13px;
}
.popup-content {
  padding: 10px 14px;
}
.popup-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 0;
  font-size: 12px;
  border-bottom: 1px solid #f0f0f0;
}
.popup-row:last-child {
  border-bottom: none;
}
.popup-label {
  color: #666;
  font-weight: 500;
}
.popup-value {
  color: #333;
  font-weight: 600;
}
.popup-empty {
  color: #999;
  font-size: 12px;
  text-align: center;
  padding: 8px 0;
}
.resident-dot {
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  transition: all 0.2s ease;
  cursor: pointer;
}
.resident-dot:hover {
  transform: scale(1.3);
}

:deep(.town-label-transparent) {
  background: transparent !important;
  border: none !important;
  box-shadow: none !important;
  color: #1f2937;
  font-weight: 800;
  font-size: 13px;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  text-shadow: 
    -1px -1px 0 rgba(255,255,255,1),  
     1px -1px 0 rgba(255,255,255,1),
    -1px  1px 0 rgba(255,255,255,1),
     1px  1px 0 rgba(255,255,255,1),
     0px  0px 2px rgba(255,255,255,1);
  padding: 0;
  margin-left: 2px;
  pointer-events: none;
}
:deep(.town-label-transparent::before) {
  display: none !important;
}
</style>