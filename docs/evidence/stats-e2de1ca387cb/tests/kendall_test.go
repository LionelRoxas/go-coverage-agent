package stats

import (
	"errors"
	"math"
	"testing"
)

func TestKendallTau(t *testing.T) {
	tests := []struct {
		name    string
		x, y    Float64Data
		want    float64
		wantErr error
	}{
		{"empty input", Float64Data{}, Float64Data{1, 2}, math.NaN(), ErrEmptyInput},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1, 2, 3}, math.NaN(), ErrSize},
		{"single element", Float64Data{5}, Float64Data{10}, 0, nil},
		{"perfect concordance", Float64Data{1, 2, 3}, Float64Data{1, 2, 3}, 1, nil},
		{"ties in first", Float64Data{1, 1, 2}, Float64Data{1, 2, 3}, 2.0 / math.Sqrt(6.0), nil},
		{"ties in second", Float64Data{1, 2, 3}, Float64Data{1, 1, 2}, 2.0 / math.Sqrt(6.0), nil},
	}
	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := KendallTau(tc.x, tc.y)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.IsNaN(tc.want) {
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN, got %v", got)
				}
			} else {
				if math.Abs(got-tc.want) > 1e-9 {
					t.Fatalf("got %v, want %v", got, tc.want)
				}
			}
		})
	}
}

func TestFloat64Data_KendallTau(t *testing.T) {
	// normal case, should match function result
	x := Float64Data{1, 2, 3}
	y := Float64Data{1, 2, 3}
	got, err := x.KendallTau(y)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if math.Abs(got-1) > 1e-9 {
		t.Fatalf("method result %v, want 1", got)
	}
	// error propagation for empty input
	_, err = Float64Data{}.KendallTau(y)
	if err == nil || !errors.Is(err, ErrEmptyInput) {
		t.Fatalf("expected ErrEmptyInput, got %v", err)
	}
}
