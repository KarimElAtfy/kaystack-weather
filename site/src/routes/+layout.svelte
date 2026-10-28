<script lang="ts">
  import '../styles/layers.css';
  import '../styles/tokens.css';
  import '../styles/base.css';
  import '../styles/layout.css';
  import '../styles/legacy.css';

  let { children } = $props();
</script>

{@render children()}
