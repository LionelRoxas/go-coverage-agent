package stats

import (
	"errors"
	"math"
	"testing"
)

func geometricDistributionProbSum(a, b int, p float64) float64 {
	q := 1 - p
	sum := 0.0
	for k := a; k <= b; k++ {
		sum += p * math.Pow(q, float64(k-1))
	}
	return sum
}

func TestProbGeom_ErrorsAndValues(t *testing.T) {
	cases := []struct {
		name    string
		a, b    int
		p       float64
		want    float64
		wantErr error
	}{
		{"a less than 1", 0, 5, 0.5, math.NaN(), ErrBounds},
		{"a greater than b", 5, 3, 0.5, math.NaN(), ErrBounds},
		{"single trial", 3, 3, 0.5, 0.5 * math.Pow(0.5, 2), nil},
		{"multiple trials", 2, 4, 0.5, geometricDistributionProbSum(2, 4, 0.5), nil},
		{"different p", 1, 3, 0.2, geometricDistributionProbSum(1, 3, 0.2), nil},
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
				return
			}
			if math.Abs(got-tc.want) > 1e-12 {
				t.Fatalf("ProbGeom(%d,%d,%v) = %v, want %v", tc.a, tc.b, tc.p, got, tc.want)
			}
		})
	}
}

func TestExpGeom_ErrorsAndValues(t *testing.T) {
	cases := []struct {
		name    string
		p       float64
		want    float64
		wantErr error
	}{
		{"negative p", -0.1, math.NaN(), ErrNegative},
		{"p greater than 1", 1.5, math.NaN(), ErrNegative},
		{"valid p", 0.25, 4.0, nil},
		{"p zero", 0.0, math.Inf(1), nil},
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
					t.Fatalf("expected NaN result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.IsInf(tc.want, 1) {
				if !math.IsInf(got, 1) {
					t.Fatalf("expected +Inf, got %v", got)
				}
				return
			}
			if math.Abs(got-tc.want) > 1e-12 {
				t.Fatalf("ExpGeom(%v) = %v, want %v", tc.p, got, tc.want)
			}
		})
	}
}

func TestVarGeom_ErrorsAndValues(t *testing.T) {
	cases := []struct {
		name    string
		p       float64
		want    float64
		wantErr error
	}{
		{"negative p", -0.2, math.NaN(), ErrNegative},
		{"p greater than 1", 2.0, math.NaN(), ErrNegative},
		{"valid p", 0.5, (1 - 0.5) / math.Pow(0.5, 2), nil},
		{"p zero", 0.0, math.Inf(1), nil},
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
					t.Fatalf("expected NaN result on error, got %v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if math.IsInf(tc.want, 1) {
				if !math.IsInf(got, 1) {
					t.Fatalf("expected +Inf, got %v", got)
				}
				return
			}
			if math.Abs(got-tc.want) > 1e-12 {
				t.Fatalf("VarGeom(%v) = %v, want %v", tc.p, got, tc.want)
			}
		})
	}
}
