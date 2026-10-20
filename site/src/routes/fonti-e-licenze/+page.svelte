<script lang="ts">
  import TextPage from '#lib/ui/TextPage.svelte';

  let { data } = $props();
</script>

<TextPage towns={data.towns} name="sources" title="page.sources.title" />
