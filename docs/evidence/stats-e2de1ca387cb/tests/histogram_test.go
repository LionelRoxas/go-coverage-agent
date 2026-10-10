package stats

import (
	"errors"
	"math"
	"testing"
)

func TestHistogram(t *testing.T) {
	cases := []struct {
		name      string
		input     []float64
		bins      int
		wantErr   error
		wantCnt   []int
		wantEdges []float64
	}{
		{
			name:    "empty input returns ErrEmptyInput",
			input:   []float64{},
			bins:    3,
			wantErr: ErrEmptyInput,
		},
		{
			name:    "bins less than one returns ErrBounds",
			input:   []float64{1, 2, 3},
			bins:    0,
			wantErr: ErrBounds,
		},
		{
			name:    "all equal values expands range",
			input:   []float64{5, 5, 5},
			bins:    3,
			wantErr: nil,
			wantCnt: []int{0, 3, 0},
			// edges: [4.5, 4.833333..., 5.166666..., 5.5]
			wantEdges: []float64{4.5, 4.5 + (5.5-4.5)/3, 4.5 + 2*(5.5-4.5)/3, 5.5},
		},
		{
			name:      "max value falls into last bin",
			input:     []float64{0, 10},
			bins:      2,
			wantErr:   nil,
			wantCnt:   []int{1, 1},
			wantEdges: []float64{0, 5, 10},
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			cnt, edges, err := Histogram(tc.input, tc.bins)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			// compare counts
			if len(cnt) != len(tc.wantCnt) {
				t.Fatalf("counts length mismatch: got %d, want %d", len(cnt), len(tc.wantCnt))
			}
			for i := range cnt {
				if cnt[i] != tc.wantCnt[i] {
					t.Fatalf("counts mismatch at %d: got %d, want %d", i, cnt[i], tc.wantCnt[i])
				}
			}
			// compare edges with tolerance
			if len(edges) != len(tc.wantEdges) {
				t.Fatalf("edges length mismatch: got %d, want %d", len(edges), len(tc.wantEdges))
			}
			const eps = 1e-9
			for i := range edges {
				if math.Abs(edges[i]-tc.wantEdges[i]) > eps {
					t.Fatalf("edge %d mismatch: got %v, want %v", i, edges[i], tc.wantEdges[i])
				}
			}
		})
	}
}

func TestFloat64Data_Histogram(t *testing.T) {
	data := Float64Data{1, 2, 3, 4, 5}
	bins := 2
	cnt, edges, err := data.Histogram(bins)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	// Expected edges: min=1, max=5, width=2, edges=[1,3,5]
	expEdges := []float64{1, 3, 5}
	const eps = 1e-9
	for i := range edges {
		if math.Abs(edges[i]-expEdges[i]) > eps {
			t.Fatalf("edge %d mismatch: got %v, want %v", i, edges[i], expEdges[i])
		}
	}
	// Values 1,2 go to first bin; 3,4,5 to second (max goes to last bin)
	expCnt := []int{2, 3}
	if len(cnt) != len(expCnt) {
		t.Fatalf("counts length mismatch: got %d, want %d", len(cnt), len(expCnt))
	}
	for i := range cnt {
		if cnt[i] != expCnt[i] {
			t.Fatalf("counts mismatch at %d: got %d, want %d", i, cnt[i], expCnt[i])
		}
	}
}
