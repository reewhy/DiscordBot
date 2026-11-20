<script setup>
import { ref } from 'vue'
import { actions } from '../store'
import { BASE, thumbUrl } from '../discord'

const query = ref('')
const results = ref([])
const loading = ref(false)
const error = ref('')
const searched = ref(false)
const justAdded = ref(null)

async function search() {
  const q = query.value.trim()
  if (q.length < 2) return
  loading.value = true
  error.value = ''
  try {
    const res = await fetch(`${BASE}/api/search?q=${encodeURIComponent(q)}`)
    const data = await res.json()
    if (!res.ok) throw new Error(data.error || 'Ricerca non riuscita')
    results.value = data.results
    searched.value = true
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

function add(r) {
  actions.add(r)
  justAdded.value = r.videoId
  setTimeout(() => (justAdded.value = null), 1500)
}
</script>

<template>
  <section class="panel">
    <h2 class="panel-title">Cerca una canzone</h2>
    <form class="search" @submit.prevent="search">
      <input v-model="query" type="search" placeholder="Titolo o artista" aria-label="Titolo o artista" />
      <button class="btn btn-main" :disabled="loading || query.trim().length < 2">
        {{ loading ? 'Cerco…' : 'Cerca' }}
      </button>
    </form>
    <p class="hint">Aggiungiamo “karaoke” alla ricerca per te.</p>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-else-if="searched && !results.length" class="hint">Nessun risultato. Prova con un altro titolo.</p>

    <ul class="list">
      <li v-for="r in results" :key="r.videoId" class="row">
        <img :src="thumbUrl(r.videoId)" alt="" loading="lazy" />
        <div class="meta">
          <strong>{{ r.title }}</strong>
          <span>{{ r.channel }}</span>
        </div>
        <button class="btn" @click="add(r)">
          {{ justAdded === r.videoId ? 'Aggiunta' : 'Aggiungi' }}
        </button>
      </li>
    </ul>
  </section>
</template>
