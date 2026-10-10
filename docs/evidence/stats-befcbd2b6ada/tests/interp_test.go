package stats

import (
	"errors"
	"math"
	"testing"
)

func interpFloatEqual(got, want float64) bool {
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= 1e-9
}

func TestInterp_EmptyInput(t *testing.T) {
	cases := []struct {
		name      string
		x, xp, fp Float64Data
		wantErr   error
	}{
		{"empty x", Float64Data{}, Float64Data{0, 1}, Float64Data{0, 1}, ErrEmptyInput},
		{"empty xp", Float64Data{0}, Float64Data{}, Float64Data{}, ErrEmptyInput},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := Interp(tc.x, tc.xp, tc.fp)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestInterp_SizeMismatch(t *testing.T) {
	x := Float64Data{0}
	xp := Float64Data{0, 1}
	fp := Float64Data{0}
	_, err := Interp(x, xp, fp)
	if !errors.Is(err, ErrSize) {
		t.Fatalf("expected ErrSize, got %v", err)
	}
}

func TestInterp_BoundsChecks(t *testing.T) {
	cases := []struct {
		name    string
		xp, fp  Float64Data
		wantErr error
	}{
		{"NaN in xp", Float64Data{math.NaN(), 1}, Float64Data{0, 1}, ErrBounds},
		{"non‑increasing xp", Float64Data{0, 0, 1}, Float64Data{0, 0, 1}, ErrBounds},
	}
	x := Float64Data{0.5}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := Interp(x, tc.xp, tc.fp)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestInterp_Values(t *testing.T) {
	xp := Float64Data{0, 10}
	fp := Float64Data{0, 100}
	cases := []struct {
		name string
		x    Float64Data
		want []float64
	}{
		{"NaN x", Float64Data{math.NaN()}, []float64{math.NaN()}},
		{"below range", Float64Data{-5}, []float64{0}},
		{"above range", Float64Data{15}, []float64{100}},
		{"exact knot", Float64Data{10}, []float64{100}},
		{"interpolate", Float64Data{5}, []float64{50}},
		{"multiple values", Float64Data{-5, 0, 5, 10, 15}, []float64{0, 0, 50, 100, 100}},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Interp(tc.x, xp, fp)
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if len(got) != len(tc.want) {
				t.Fatalf("len mismatch: got %d want %d", len(got), len(tc.want))
			}
			for i := range got {
				if math.IsNaN(tc.want[i]) {
					if !math.IsNaN(got[i]) {
						t.Errorf("index %d: expected NaN, got %v", i, got[i])
					}
				} else if !interpFloatEqual(got[i], tc.want[i]) {
					t.Errorf("index %d: got %v want %v", i, got[i], tc.want[i])
				}
			}
		})
	}

	t.Run("inf spacing", func(t *testing.T) {
		xpInf := Float64Data{1, math.Inf(1)}
		fpInf := Float64Data{0, 1}
		x := Float64Data{2}
		got, err := Interp(x, xpInf, fpInf)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if len(got) != 1 {
			t.Fatalf("len mismatch")
		}
		if got[0] != 0 {
			t.Errorf("expected 0 due to overflow handling, got %v", got[0])
		}
	})
}

func TestInterp_ExactKnot(t *testing.T) {
	cases := []struct {
		name      string
		x, xp, fp Float64Data
		want      []float64
		wantErr   error
	}{
		{
			name:    "exact knot returns fp directly and interpolates others",
			x:       Float64Data{1.0, 2.0, 2.5, 3.0},
			xp:      Float64Data{1.0, 2.0, 3.0},
			fp:      Float64Data{10.0, 20.0, 30.0},
			want:    []float64{10.0, 20.0, 25.0, 30.0},
			wantErr: nil,
		},
	}

	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Interp(tc.x, tc.xp, tc.fp)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if len(got) != len(tc.want) {
				t.Fatalf("result length mismatch: got %d, want %d", len(got), len(tc.want))
			}
			for i := range got {
				if !interpFloatEqual(got[i], tc.want[i]) {
					t.Errorf("index %d: got %v, want %v", i, got[i], tc.want[i])
				}
			}
		})
	}
}
