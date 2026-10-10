package stats

import (
	"errors"
	"math"
	"testing"
)

func geometricDistributionApproxEqual(got, want float64) bool {
	if math.IsNaN(got) && math.IsNaN(want) {
		return true
	}
	return math.Abs(got-want) <= 1e-9
}

func TestProbGeom_Uncovered(t *testing.T) {
	cases := []struct {
		name    string
		a, b    int
		p       float64
		want    float64
		wantErr error
	}{
		{"InvalidBounds_AgtB", 5, 3, 0.5, math.NaN(), ErrBounds},
		{"InvalidBounds_Alt1", 0, 2, 0.5, math.NaN(), ErrBounds},
		{"SingleTrial", 3, 3, 0.4, 0.4 * math.Pow(0.6, 2), nil},
		{"Range", 2, 5, 0.3, math.Pow(0.7, 1) * -math.Expm1(float64(5-2+1)*math.Log1p(-0.3)), nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := ProbGeom(tc.a, tc.b, tc.p)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !geometricDistributionApproxEqual(got, tc.want) {
				t.Fatalf("ProbGeom(%d,%d,%v) = %v, want %v", tc.a, tc.b, tc.p, got, tc.want)
			}
		})
	}
}

func TestExpGeom_Uncovered(t *testing.T) {
	cases := []struct {
		name    string
		p       float64
		want    float64
		wantErr error
	}{
		{"InvalidNeg", -0.1, math.NaN(), ErrNegative},
		{"InvalidAbove", 1.2, math.NaN(), ErrNegative},
		{"Valid", 0.25, 4.0, nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := ExpGeom(tc.p)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !geometricDistributionApproxEqual(got, tc.want) {
				t.Fatalf("ExpGeom(%v) = %v, want %v", tc.p, got, tc.want)
			}
		})
	}
}

func TestVarGeom_Uncovered(t *testing.T) {
	cases := []struct {
		name    string
		p       float64
		want    float64
		wantErr error
	}{
		{"InvalidNeg", -0.05, math.NaN(), ErrNegative},
		{"InvalidAbove", 2.0, math.NaN(), ErrNegative},
		{"Valid", 0.2, (1 - 0.2) / math.Pow(0.2, 2), nil},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := VarGeom(tc.p)
			if tc.wantErr != nil {
				if err == nil || !errors.Is(err, tc.wantErr) {
					t.Fatalf("expected error %v, got %v", tc.wantErr, err)
				}
				if !math.IsNaN(got) {
					t.Fatalf("expected NaN result, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if !geometricDistributionApproxEqual(got, tc.want) {
				t.Fatalf("VarGeom(%v) = %v, want %v", tc.p, got, tc.want)
			}
		})
	}
}
