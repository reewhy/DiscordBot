<script setup>
import { state, actions } from '../store'
import { thumbUrl } from '../discord'
</script>

<template>
  <section class="panel">
    <h2 class="panel-title">In coda</h2>
    <p v-if="!state.room.queue.length" class="hint">Nessuno in attesa. Aggiungi un brano dalla ricerca.</p>
    <ul class="list">
      <li v-for="t in state.room.queue" :key="t.qid" class="row">
        <img :src="thumbUrl(t.videoId)" alt="" loading="lazy" />
        <div class="meta">
          <strong>{{ t.title }}</strong>
          <span>Canta {{ t.addedBy.username }}</span>
        </div>
        <button class="btn" @click="actions.remove(t.qid)">Rimuovi</button>
      </li>
    </ul>
  </section>
</template>
