<template>
  <div class="landing" role="main">
    <div class="landing-bg" aria-hidden="true">
      <div class="orb orb-a" />
      <div class="orb orb-b" />
      <div class="orb orb-c" />
      <div class="grid-overlay" />
    </div>

    <div class="landing-inner">
      <p class="eyebrow">{{ t('landing.eyebrow') }}</p>
      <h1 class="hero-title">
        <span class="hero-gradient">{{ t('landing.heroTitle') }}</span>
      </h1>
      <p class="hero-lead">{{ t('landing.heroLead') }}</p>

      <div class="cta-row">
        <el-button type="primary" size="large" class="cta-primary" round @click="$emit('enter')">
          {{ t('landing.ctaWorkbench') }}
        </el-button>
        <el-button size="large" round class="cta-ghost" @click="$emit('enter-ai')">
          {{ t('landing.ctaAi') }}
        </el-button>
      </div>
      <p class="nav-hint">{{ t('landing.navHint') }}</p>

      <section class="pillars" aria-label="Core innovations">
        <article v-for="(p, i) in pillars" :key="i" class="pillar-card">
          <div class="pillar-icon" aria-hidden="true">{{ p.icon }}</div>
          <h2 class="pillar-title">{{ p.title }}</h2>
          <p class="pillar-text">{{ p.body }}</p>
        </article>
      </section>

      <section class="modes" aria-label="Usage modes">
        <div class="modes-header">
          <h2>{{ t('landing.modesTitle') }}</h2>
          <p class="modes-sub">{{ t('landing.modesSub') }}</p>
        </div>
        <div class="modes-grid">
          <div class="mode-card mode-a">
            <span class="mode-tag">{{ t('landing.mode1Tag') }}</span>
            <h3>{{ t('landing.mode1Title') }}</h3>
            <p>{{ t('landing.mode1Body') }}</p>
          </div>
          <div class="mode-card mode-b">
            <span class="mode-tag accent">{{ t('landing.mode2Tag') }}</span>
            <h3>{{ t('landing.mode2Title') }}</h3>
            <p>{{ t('landing.mode2Body') }}</p>
          </div>
        </div>
      </section>

      <p class="footnote">{{ t('landing.footnote') }}</p>
    </div>
  </div>
</template>

<script setup>
import { computed, inject } from 'vue'

const useI18nFunc = inject('useI18n')
const { t } = useI18nFunc()

defineEmits(['enter', 'enter-ai'])

const pillars = computed(() => [
  {
    icon: '🌪️',
    title: t('landing.pillar1Title'),
    body: t('landing.pillar1Body')
  },
  {
    icon: '⏪',
    title: t('landing.pillar2Title'),
    body: t('landing.pillar2Body')
  },
  {
    icon: '🤖',
    title: t('landing.pillar3Title'),
    body: t('landing.pillar3Body')
  }
])
</script>

<style scoped>
.landing {
  position: relative;
  min-height: 100%;
  overflow-x: hidden;
  overflow-y: auto;
  color: #1a1a2e;
}

.landing-bg {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(72px);
  opacity: 0.55;
  animation: float 18s ease-in-out infinite;
}

.orb-a {
  width: 420px;
  height: 420px;
  background: radial-gradient(circle at 30% 30%, #5b8cff, transparent 70%);
  top: -120px;
  right: -80px;
  animation-delay: 0s;
}

.orb-b {
  width: 380px;
  height: 380px;
  background: radial-gradient(circle at 70% 70%, #36cfc9, transparent 70%);
  bottom: 10%;
  left: -100px;
  animation-delay: -6s;
}

.orb-c {
  width: 300px;
  height: 300px;
  background: radial-gradient(circle at 50% 50%, #a78bfa, transparent 65%);
  top: 40%;
  right: 15%;
  opacity: 0.35;
  animation-delay: -12s;
}

.grid-overlay {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(64, 158, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(64, 158, 255, 0.06) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse 80% 60% at 50% 20%, black, transparent);
}

@keyframes float {
  0%,
  100% {
    transform: translate(0, 0) scale(1);
  }
  33% {
    transform: translate(24px, -20px) scale(1.05);
  }
  66% {
    transform: translate(-16px, 12px) scale(0.98);
  }
}

.landing-inner {
  position: relative;
  z-index: 1;
  max-width: 1080px;
  margin: 0 auto;
  padding: 32px 28px 48px;
  text-align: center;
}

.eyebrow {
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: #409eff;
  margin-bottom: 16px;
  padding: 6px 14px;
  border-radius: 999px;
  background: rgba(64, 158, 255, 0.12);
  border: 1px solid rgba(64, 158, 255, 0.25);
}

.hero-title {
  font-size: clamp(2rem, 5vw, 3.25rem);
  font-weight: 800;
  line-height: 1.12;
  letter-spacing: -0.03em;
  margin: 0 0 16px;
}

.hero-gradient {
  background: linear-gradient(120deg, #1d4ed8 0%, #409eff 35%, #36cfc9 70%, #0891b2 100%);
  background-size: 200% auto;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: shine 8s ease-in-out infinite;
}

@keyframes shine {
  0%,
  100% {
    background-position: 0% center;
  }
  50% {
    background-position: 100% center;
  }
}

.hero-lead {
  font-size: clamp(1rem, 2.2vw, 1.2rem);
  line-height: 1.65;
  color: #4b5563;
  max-width: 720px;
  margin: 0 auto 28px;
}

.cta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  justify-content: center;
  margin-bottom: 14px;
}

.nav-hint {
  font-size: 0.82rem;
  color: #6b7280;
  margin: 0 0 40px;
  line-height: 1.5;
}

.cta-primary {
  padding: 12px 28px;
  font-weight: 600;
  box-shadow: 0 8px 28px rgba(64, 158, 255, 0.35);
}

.cta-ghost {
  font-weight: 600;
  border: 1px solid rgba(64, 158, 255, 0.45);
  background: rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(8px);
}

.pillars {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 18px;
  margin-bottom: 40px;
  text-align: left;
}

@media (max-width: 900px) {
  .pillars {
    grid-template-columns: 1fr;
  }
}

.pillar-card {
  padding: 22px 20px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid rgba(255, 255, 255, 0.9);
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.08);
  backdrop-filter: blur(12px);
  transition: transform 0.25s ease, box-shadow 0.25s ease;
}

.pillar-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 20px 48px rgba(15, 23, 42, 0.12);
}

.pillar-icon {
  font-size: 28px;
  margin-bottom: 10px;
}

.pillar-title {
  font-size: 1.05rem;
  font-weight: 700;
  margin: 0 0 10px;
  color: #111827;
}

.pillar-text {
  font-size: 0.9rem;
  line-height: 1.55;
  color: #6b7280;
  margin: 0;
}

.modes {
  text-align: left;
  margin-bottom: 32px;
}

.modes-header {
  text-align: center;
  margin-bottom: 20px;
}

.modes-header h2 {
  font-size: 1.35rem;
  font-weight: 800;
  margin: 0 0 8px;
  color: #111827;
}

.modes-sub {
  font-size: 0.95rem;
  color: #6b7280;
  margin: 0;
}

.modes-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px;
}

@media (max-width: 720px) {
  .modes-grid {
    grid-template-columns: 1fr;
  }
}

.mode-card {
  padding: 22px 20px;
  border-radius: 16px;
  border: 1px solid rgba(64, 158, 255, 0.15);
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.9), rgba(240, 249, 255, 0.85));
}

.mode-card h3 {
  font-size: 1.05rem;
  margin: 10px 0 8px;
  color: #111827;
}

.mode-card p {
  font-size: 0.88rem;
  line-height: 1.55;
  color: #4b5563;
  margin: 0;
}

.mode-tag {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: #2563eb;
  background: rgba(37, 99, 235, 0.1);
  padding: 4px 10px;
  border-radius: 6px;
}

.mode-tag.accent {
  color: #0d9488;
  background: rgba(13, 148, 136, 0.12);
}

.footnote {
  font-size: 0.8rem;
  color: #9ca3af;
  margin: 0;
}
</style>
