"""Automated system prompt optimization loop."""
from dataclasses import dataclass
from pathlib import Path
import sqlite3
import time
import uuid

import requests

MUTATION_FILES = {
    'rephrase': 'rephrase.txt',
    'add_constraints': 'add_constraints.txt',
    'add_examples': 'add_examples.txt',
}


class OptimizationError(Exception):
    """Optimizer failure that should be shown without traceback."""


@dataclass
class OptimizationResult:
    optimized_prompt: str
    best_score: float
    history: list[dict]
    iterations: int
    converged: bool


class PromptOptimizer:
    def __init__(self, model, host='http://localhost:11434', timeout=30, max_iterations=10,
                 improvement_threshold=0.01, plateau_rounds=3,
                 db_path='optimization/history.sqlite3', prompts_dir=None,
                 variant_generator=None):
        if not isinstance(max_iterations, int) or max_iterations <= 0:
            raise OptimizationError('max_iterations must be a positive integer.')
        if not isinstance(plateau_rounds, int) or plateau_rounds <= 0:
            raise OptimizationError('plateau_rounds must be a positive integer.')
        if improvement_threshold < 0:
            raise OptimizationError('improvement_threshold must be non-negative.')
        self.model = model
        self.host = host.rstrip('/')
        self.timeout = timeout
        self.max_iterations = max_iterations
        self.improvement_threshold = improvement_threshold
        self.plateau_rounds = plateau_rounds
        self.db_path = Path(db_path)
        self.prompts_dir = Path(prompts_dir) if prompts_dir else (
            Path(__file__).resolve().parent.parent / 'prompts' / 'optimization'
        )
        self.variant_generator = variant_generator or self._generate_with_ollama
        self._mutation_templates = self._load_mutation_templates()
        self._setup_database()

    def optimize(self, initial_prompt, ev1_evaluator, retrieval_context=''):
        if not isinstance(initial_prompt, str) or not initial_prompt.strip():
            raise OptimizationError('initial_prompt must be a non-empty string.')
        if not callable(ev1_evaluator):
            raise OptimizationError('ev1_evaluator must be callable.')

        run_id = uuid.uuid4().hex
        history = []
        best_prompt = initial_prompt.strip()
        best_score = float(ev1_evaluator(best_prompt, retrieval_context))
        self._record(run_id, history, 0, 'baseline', best_prompt, best_score, True)

        plateau_count = 0
        converged = False
        completed_iterations = 0
        for iteration in range(1, self.max_iterations + 1):
            candidates = self._generate_variants(best_prompt, retrieval_context)
            if not candidates:
                break

            best_candidate = None
            for strategy, prompt in candidates:
                score = float(ev1_evaluator(prompt, retrieval_context))
                row = self._record(run_id, history, iteration, strategy, prompt, score, False)
                if best_candidate is None or score > best_candidate['score']:
                    best_candidate = row
            best_candidate['selected'] = True
            self._update_selected(run_id, iteration, best_candidate['strategy'], best_candidate['prompt'])

            previous_score = best_score
            if best_candidate['score'] > best_score:
                best_score = best_candidate['score']
                best_prompt = best_candidate['prompt']
            improvement = self._relative_improvement(previous_score, best_score)
            plateau_count = plateau_count + 1 if improvement < self.improvement_threshold else 0
            completed_iterations = iteration
            if plateau_count >= self.plateau_rounds:
                converged = True
                break

        return OptimizationResult(
            optimized_prompt=best_prompt,
            best_score=best_score,
            history=history,
            iterations=completed_iterations,
            converged=converged,
        )

    def _generate_variants(self, prompt, retrieval_context):
        variants = []
        seen = {prompt}
        for strategy, template in self._mutation_templates.items():
            instruction = template.format(prompt=prompt, context=retrieval_context)
            candidate = self.variant_generator(prompt, strategy, instruction)
            if not isinstance(candidate, str):
                continue
            candidate = candidate.strip()
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            variants.append((strategy, candidate))
        return variants

    def _generate_with_ollama(self, prompt, strategy, instruction):
        del prompt, strategy
        payload = {
            'model': self.model,
            'stream': False,
            'messages': [
                {'role': 'system', 'content': 'Rewrite prompts. Return only the final prompt text.'},
                {'role': 'user', 'content': instruction},
            ],
        }
        try:
            response = requests.post(
                self.host + '/api/chat',
                json=payload,
                timeout=(5, self.timeout),
            )
        except requests.RequestException as error:
            raise OptimizationError(f'Failed to generate candidate with Ollama: {error}') from error
        if not response.ok:
            raise OptimizationError(f'Ollama error {response.status_code}: {response.text[:300]}')
        try:
            data = response.json()
        except ValueError as error:
            raise OptimizationError('Ollama returned invalid JSON.') from error
        message = data.get('message') if isinstance(data, dict) else None
        content = message.get('content') if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise OptimizationError('Ollama did not return a valid prompt candidate.')
        return content.strip()

    def _load_mutation_templates(self):
        templates = {}
        for strategy, file_name in MUTATION_FILES.items():
            path = self.prompts_dir / file_name
            try:
                content = path.read_text(encoding='utf-8').strip()
            except OSError as error:
                raise OptimizationError(
                    f'Cannot load mutation prompt for {strategy!r}: {path}'
                ) from error
            if not content:
                raise OptimizationError(f'Mutation prompt for {strategy!r} is empty: {path}')
            templates[strategy] = content
        return templates

    @staticmethod
    def _relative_improvement(previous_score, new_score):
        if new_score <= previous_score:
            return 0.0
        if previous_score == 0:
            return float('inf')
        return (new_score - previous_score) / abs(previous_score)

    def _setup_database(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path)
        try:
            with connection:
                connection.execute(
                    'CREATE TABLE IF NOT EXISTS optimization_history ('
                    'run_id TEXT NOT NULL, iteration INTEGER NOT NULL, strategy TEXT NOT NULL, '
                    'prompt TEXT NOT NULL, score REAL NOT NULL, selected INTEGER NOT NULL, '
                    'created_at REAL NOT NULL)'
                )
        finally:
            connection.close()

    def _record(self, run_id, history, iteration, strategy, prompt, score, selected):
        row = {
            'run_id': run_id,
            'iteration': iteration,
            'strategy': strategy,
            'prompt': prompt,
            'score': score,
            'selected': bool(selected),
        }
        history.append(row)
        connection = sqlite3.connect(self.db_path)
        try:
            with connection:
                connection.execute(
                    'INSERT INTO optimization_history '
                    '(run_id, iteration, strategy, prompt, score, selected, created_at) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (run_id, iteration, strategy, prompt, score, int(selected), time.time()),
                )
        finally:
            connection.close()
        return row

    def _update_selected(self, run_id, iteration, strategy, prompt):
        connection = sqlite3.connect(self.db_path)
        try:
            with connection:
                connection.execute(
                    'UPDATE optimization_history SET selected = 1 '
                    'WHERE run_id = ? AND iteration = ? AND strategy = ? AND prompt = ?',
                    (run_id, iteration, strategy, prompt),
                )
        finally:
            connection.close()
