<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { state, actions, expectedPosition } from '../store'
import { isEmbedded } from '../discord'

const host = ref(null)
const needsTap = ref(false)
const pos = ref(0)
const duration = ref(0)
const dragging = ref(false)

let player = null
let ready = false
let loadedQid = null
let tapTimer = null
let tickTimer = null
let driftTimer = null

const current = computed(() => state.room.current)
const playing = computed(() => state.room.status === 'playing')
const YTS = () => window.YT.PlayerState

function loadApi() {
  return new Promise((resolve) => {
    if (window.YT?.Player) return resolve()
    window.onYouTubeIframeAPIReady = resolve
    const s = document.createElement('script')
    s.src = `${isEmbedded ? '/.proxy/youtube' : 'https://www.youtube.com'}/iframe_api`
    document.head.appendChild(s)
  })
}

// Porta il player allo stato condiviso (brano, play/pausa, posizione).
function apply() {
  if (!ready) return
  const cur = state.room.current
  if (!cur) {
    player.stopVideo()
    loadedQid = null
    needsTap.value = false
    return
  }

  const target = expectedPosition()

  if (loadedQid !== cur.qid) {
    loadedQid = cur.qid
    const args = { videoId: cur.videoId, startSeconds: target }
    if (playing.value) {
      player.loadVideoById(args)
      watchAutoplay()
    } else {
      player.cueVideoById(args)
    }
    return
  }

  if (playing.value) {
    if (player.getPlayerState() !== YTS().PLAYING) player.playVideo()
    if (Math.abs(player.getCurrentTime() - target) > 2) player.seekTo(target, true)
  } else {
    player.pauseVideo()
    const p = state.room.position
    if (Math.abs(player.getCurrentTime() - p) > 1) player.seekTo(p, true)
  }
}

// Se il browser blocca l'autoplay mostriamo un pulsante da toccare.
function watchAutoplay() {
  needsTap.value = false
  clearTimeout(tapTimer)
  tapTimer = setTimeout(() => {
    const st = player.getPlayerState()
    if (playing.value && st !== YTS().PLAYING && st !== YTS().BUFFERING) needsTap.value = true
  }, 2500)
}

function tap() {
  needsTap.value = false
  player.playVideo()
  player.seekTo(expectedPosition(), true)
}

function onStateChange(e) {
  if (e.data === YTS().PLAYING) needsTap.value = false
  if (e.data === YTS().ENDED && state.room.current) actions.ended(state.room.current.qid)
}

onMounted(async () => {
  await loadApi()
  const options = {
    width: '100%',
    height: '100%',
    playerVars: { controls: 0, disablekb: 1, rel: 0, modestbranding: 1, playsinline: 1, fs: 0, iv_load_policy: 3 },
    events: {
      onReady: () => {
        ready = true
        apply()
      },
      onStateChange
    }
  }
  // Dentro Discord l'iframe del player deve essere servito dal proxy.
  if (isEmbedded) options.host = `${window.location.origin}/.proxy/youtube`
  player = new window.YT.Player(host.value, options)

  tickTimer = setInterval(() => {
    if (!ready || dragging.value) return
    const d = player.getDuration?.() || 0
    if (d > 0) duration.value = d
    pos.value = Math.min(expectedPosition(), duration.value || Infinity)
  }, 500)

  // Correzione della deriva: se siamo fuori di oltre 2,5 s ci riallineiamo.
  driftTimer = setInterval(() => {
    if (!ready || !playing.value || !state.room.current) return
    if (player.getPlayerState() !== YTS().PLAYING) return
    if (Math.abs(player.getCurrentTime() - expectedPosition()) > 2.5) {
      player.seekTo(expectedPosition(), true)
    }
  }, 3000)
})

onBeforeUnmount(() => {
  clearInterval(tickTimer)
  clearInterval(driftTimer)
  clearTimeout(tapTimer)
  player?.destroy?.()
})

watch(() => state.room, apply)

const fmt = (s) => {
  const t = Math.max(0, Math.floor(s || 0))
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, '0')}`
}

function commitSeek(e) {
  dragging.value = false
  actions.seek(Number(e.target.value))
}
const skip = (delta) => actions.seek(Math.max(0, expectedPosition() + delta))
</script>

<template>
  <section class="stage">
    <div class="video">
      <div class="yt"><div ref="host"></div></div>
      <div v-if="!current" class="video-empty">
        <p>Il palco è vuoto</p>
      </div>
      <div v-else class="shield"></div>
      <button v-if="needsTap && current" class="tap" @click="tap">Tocca per avviare l’audio</button>
    </div>

    <div class="now" v-if="current">
      <p class="singer">Tocca a {{ current.addedBy.username }}</p>
      <h2 class="song">{{ current.title }}</h2>

      <div class="progress">
        <span>{{ fmt(pos) }}</span>
        <input
          type="range"
          min="0"
          :max="duration || 1"
          step="1"
          :value="pos"
          aria-label="Posizione nel brano"
          @pointerdown="dragging = true"
          @input="pos = Number($event.target.value)"
          @change="commitSeek"
        />
        <span>{{ fmt(duration) }}</span>
      </div>

      <div class="controls">
        <button class="btn" @click="skip(-10)">−10 s</button>
        <button v-if="playing" class="btn btn-main" @click="actions.pause()">Pausa</button>
        <button v-else class="btn btn-main" @click="actions.play()">Riprendi</button>
        <button class="btn" @click="skip(10)">+10 s</button>
        <button class="btn" @click="actions.next()">Salta brano</button>
      </div>
    </div>

    <div class="now" v-else>
      <h2 class="song">Nessun brano in corso</h2>
      <p class="hint">Cerca una canzone e aggiungila: parte subito.</p>
    </div>
  </section>
</template>
