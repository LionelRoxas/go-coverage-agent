package vetfail

import "sync"

// Copying a lock is flagged by `go vet` (copylocks) but not by the vet subset `go test` runs.
func Bad() {
	var mu sync.Mutex
	other := mu
	_ = other
}
