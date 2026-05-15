# Language Pair: Python → Go

**Difficulty tier**: Moderate

**Key differences**:
- Memory model: Python GC / Go GC (similar; no ownership tracking needed)
- Type system: Python dynamic / Go static with interfaces (no generics before 1.18)
- Error handling: Python exceptions / Go multi-return `value, error`
- Concurrency: Python GIL+asyncio / Go goroutines+channels
- OOP: Python classes / Go structs + interfaces (no inheritance)
- Nullability: Python `None` / Go nil + zero values

---

## Pre-Mapped Core Types

| Python | Go | Equivalence | Notes |
|---|---|---|---|
| `int` | `int64` | behavioral | Go int is platform-width; use int64 explicitly for portability |
| `float` | `float64` | structural | Both IEEE 754 double |
| `bool` | `bool` | structural | |
| `str` | `string` | structural | Go strings are immutable byte sequences (UTF-8) |
| `bytes` | `[]byte` | structural | |
| `None` | `nil` | structural | Context-dependent (nil pointer, nil interface, nil slice) |
| `list[T]` | `[]T` (slice) | structural | |
| `tuple[A,B]` | struct with fields | structural | Go has no anonymous tuples (use named struct) |
| `dict[K,V]` | `map[K]V` | behavioral | Go map iteration order is randomized intentionally |
| `set[T]` | `map[T]struct{}` | structural | |
| `Optional[T]` | `*T` or `(T, bool)` | structural | Use pointer for optional struct; bool pair for optional value |

## Standard Library Mapping

| Python | Go | Equivalence | Notes |
|---|---|---|---|
| `os.path.join` | `filepath.Join` | structural | |
| `os.listdir` | `os.ReadDir` | structural | |
| `os.environ.get` | `os.Getenv` | structural | |
| `open(f)` | `os.Open` | structural | |
| `json.dumps` | `json.Marshal` | structural | |
| `json.loads` | `json.Unmarshal` | structural | |
| `re.compile` | `regexp.MustCompile` | structural | |
| `hashlib.sha256` | `crypto/sha256` | structural | |
| `time.time()` | `time.Now().Unix()` | structural | |
| `random.random()` | `rand.Float64()` | behavioral | Different algorithm |
| `threading.Thread` | `go func(){}()` | structural | Goroutines are lighter |
| `asyncio` | goroutines + channels | structural | Different model but same concurrency goals |
| `subprocess.run` | `exec.Command` | structural | |
| `logging` | `log` or `zap` | structural | |
| `argparse` | `flag` or `cobra` | structural | |

## Common Third-Party Libraries

| Python | Go | Equivalence | Notes |
|---|---|---|---|
| `requests` | `net/http` (stdlib) | structural | No third-party needed |
| `sqlalchemy` | `database/sql` + driver | structural | |
| `pydantic` | struct + `encoding/json` tags | structural | |
| `click` | `cobra` | structural | |
| `pytest` | `testing` package (stdlib) | structural | |
| `numpy` | `gonum.org/v1/gonum` | behavioral | API differs significantly |

---

## Error Handling Pattern

**Python:**
```python
def read_file(path: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        raise IOError(f"not found: {path}")
```

**Go:**
```go
func readFile(path string) (string, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return "", fmt.Errorf("not found: %s: %w", path, err)
    }
    return string(data), nil
}
```

**Rule**: Every `try/except` block becomes a multi-return function. Each `except` clause becomes an `if err != nil` block. Maintain 1:1 mapping.

---

## Class → Struct + Interface

**Python:**
```python
class Storage:
    def __init__(self, path: str):
        self.path = path
    def read(self, key: str) -> bytes:
        ...
    def write(self, key: str, data: bytes):
        ...
```

**Go:**
```go
type Storage interface {
    Read(key string) ([]byte, error)
    Write(key string, data []byte) error
}

type FileStorage struct {
    path string
}

func NewFileStorage(path string) *FileStorage {
    return &FileStorage{path: path}
}

func (s *FileStorage) Read(key string) ([]byte, error) { ... }
func (s *FileStorage) Write(key string, data []byte) error { ... }
```

---

## Anti-Patterns

| Wrong | Why | Correct |
|---|---|---|
| `interface{}` for everything | Loses type safety | Use concrete types or generics (Go 1.18+) |
| Ignoring returned errors `_` | Hides Python exception flow | Always handle; match Python's except structure |
| Using `panic` for logic errors | Not equivalent to exceptions | Use error returns |
| Global `init()` for class-level state | Hides initialization order | Use explicit constructor functions |

## Ecosystem Gaps

| Python | Gap | Compensation |
|---|---|---|
| `dict` preserves order (3.7+) | `map` order randomized | Use `github.com/elliotchance/orderedmap` |
| Negative indices `arr[-1]` | Panics | Use `arr[len(arr)-1]` |
| `**kwargs` | No equivalent | Use variadic `options ...Option` pattern or struct |
| `@property` decorator | No equivalent | Use getter/setter methods |

## Testing Toolchain

| Python | Go | Notes |
|---|---|---|
| `pytest` | `go test ./...` | Built-in |
| `pytest.raises` | `if err == nil { t.Fatal(...) }` | |
| `unittest.mock` | `testify/mock` (or no mock — prohibited) | No mocks; use real implementations |
| `mypy` | `go vet` + compiler | |
| `black` | `gofmt` | Run: `gofmt -w .` |
| `pytest-benchmark` | `b.N` benchmark functions | |

## Build / CI

```yaml
# Source (Python):
- run: pip install -r requirements.txt && pytest

# Target (Go):
- run: go test ./...
- run: go vet ./...
- run: gofmt -l . | grep . && exit 1 || true
```
