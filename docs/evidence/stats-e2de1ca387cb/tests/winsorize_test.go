package stats

import (
	"errors"
	"math"
	"testing"
)

func TestWinsorize_ErrorsAndNormal(t *testing.T) {
	tests := []struct {
		name    string
		input   Float64Data
		percent float64
		want    []float64
		wantErr error
	}{
		{"empty input", Float64Data{}, 0.1, nil, ErrEmptyInput},
		{"percent negative", Float64Data{1, 2, 3}, -0.1, nil, ErrBounds},
		{"percent too large", Float64Data{1, 2, 3}, 0.5, nil, ErrBounds},
		{"percent NaN", Float64Data{1, 2, 3}, math.NaN(), nil, ErrBounds},
		{"percent zero copy", Float64Data{5, 3, 1, 4, 2}, 0.0, []float64{5, 3, 1, 4, 2}, nil},
		{"clamp example", Float64Data{1, 2, 3, 4, 5}, 0.2, []float64{2, 2, 3, 4, 4}, nil},
	}
	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Winsorize(tc.input, tc.percent)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr != nil {
				return
			}
			if len(got) != len(tc.want) {
				t.Fatalf("len mismatch: got %d want %d", len(got), len(tc.want))
			}
			for i := range got {
				if math.IsNaN(tc.want[i]) {
					if !math.IsNaN(got[i]) {
						t.Fatalf("index %d: expected NaN, got %v", i, got[i])
					}
				} else if got[i] != tc.want[i] {
					t.Fatalf("index %d: got %v want %v", i, got[i], tc.want[i])
				}
			}
			if tc.name == "percent zero copy" {
				// modify output and ensure input unchanged (copy semantics)
				got[0] = 999
				if tc.input[0] == 999 {
					t.Fatalf("output modification affected input slice")
				}
			}
		})
	}
}

func TestFloat64Data_Winsorize_Wrapper(t *testing.T) {
	data := Float64Data{10, 0, -5, 20}
	percent := 0.25
	got, err := data.Winsorize(percent)
	if err != nil {
		t.Fatalf("unexpected error from method: %v", err)
	}
	exp, err2 := Winsorize(data, percent)
	if err2 != nil {
		t.Fatalf("unexpected error from function: %v", err2)
	}
	if len(got) != len(exp) {
		t.Fatalf("length mismatch: got %d want %d", len(got), len(exp))
	}
	for i := range got {
		if got[i] != exp[i] {
			t.Fatalf("mismatch at index %d: %v vs %v", i, got[i], exp[i])
		}
	}
}
