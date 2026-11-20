<script setup>
import { onMounted } from 'vue'
import { state, init } from './store'
import Player from './components/Player.vue'
import Search from './components/Search.vue'
import Queue from './components/Queue.vue'

onMounted(init)

const initials = (name) => (name || '?').slice(0, 2)
</script>

<template>
  <main v-if="state.error" class="status">
    <h1>Qualcosa è andato storto</h1>
    <p>{{ state.error }}</p>
  </main>

  <main v-else-if="!state.ready" class="status">
    <h1>Accendo le luci…</h1>
    <p>Mi collego a Discord.</p>
  </main>

  <div v-else class="app">
    <header class="top">
      <h1 class="brand">Karaoke</h1>
      <ul class="people" aria-label="In sala">
        <li v-for="u in state.room.users" :key="u.id" :title="u.username">
          <img v-if="u.avatar" :src="u.avatar" :alt="u.username" />
          <span v-else>{{ initials(u.username) }}</span>
        </li>
      </ul>
    </header>

    <Player class="col-stage" />

    <div class="col-side">
      <Search />
      <Queue />
    </div>
  </div>
</template>
