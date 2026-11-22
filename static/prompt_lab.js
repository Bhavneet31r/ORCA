const strategy = document.getElementById('strategy');
const testInput = document.getElementById('testInput');
const testContext = document.getElementById('testContext');
const runPrompt = document.getElementById('runPrompt');
const runStatus = document.getElementById('runStatus');
const modelOutput = document.getElementById('modelOutput');

runPrompt.addEventListener('click', async () => {
  const input = testInput.value.trim();
  if (!input) {
    runStatus.textContent = 'Enter a test input.';
    testInput.focus();
    return;
  }

  runPrompt.disabled = true;
  runStatus.textContent = 'Running prompt...';
  modelOutput.textContent = 'Waiting for the model...';

  try {
    const response = await fetch('/api/prompt-run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        input,
        context: testContext.value,
        strategy: strategy.value,
      }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Prompt run failed.');
    runStatus.textContent = `${data.model} · ${data.prompt_version} · ${data.provider}`;
    modelOutput.textContent = data.answer;
  } catch (error) {
    runStatus.textContent = 'Prompt run unavailable';
    modelOutput.textContent = error.message;
  } finally {
    runPrompt.disabled = false;
  }
});
