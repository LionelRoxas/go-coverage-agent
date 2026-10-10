package stats

import (
	"errors"
	"math"
	"testing"
)

func correlationApproxEqual(a, b float64) bool {
	const eps = 1e-9
	if math.IsNaN(a) && math.IsNaN(b) {
		return true
	}
	return math.Abs(a-b) <= eps
}

func TestRankData(t *testing.T) {
	cases := []struct {
		name string
		data Float64Data
		want Float64Data
	}{
		{
			name: "empty slice",
			data: Float64Data{},
			want: Float64Data{},
		},
		{
			name: "ties get average rank",
			data: Float64Data{10, 20, 20, 30},
			want: Float64Data{1, 2.5, 2.5, 4},
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got := rankData(tc.data)
			if len(got) != len(tc.want) {
				t.Fatalf("expected length %d, got %d", len(tc.want), len(got))
			}
			for i := range got {
				if !correlationApproxEqual(got[i], tc.want[i]) {
					t.Fatalf("at index %d: expected %v, got %v", i, tc.want[i], got[i])
				}
			}
		})
	}
}

func TestAutoCorrelation(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		lags    int
		want    float64
		wantErr error
	}{
		{
			name:    "empty input",
			data:    Float64Data{},
			lags:    0,
			want:    0,
			wantErr: EmptyInputErr,
		},
		{
			name:    "lags out of bounds",
			data:    Float64Data{1, 2, 3},
			lags:    3,
			want:    0,
			wantErr: BoundsErr,
		},
		{
			name:    "zero variance returns 0",
			data:    Float64Data{5, 5, 5, 5},
			lags:    1,
			want:    0,
			wantErr: nil,
		},
		{
			name:    "normal case",
			data:    Float64Data{1, 2, 3, 4},
			lags:    1,
			want:    0.25,
			wantErr: nil,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := AutoCorrelation(tc.data, tc.lags)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if !correlationApproxEqual(got, tc.want) {
					t.Fatalf("expected %v, got %v", tc.want, got)
				}
			}
		})
	}
}

func TestCorrelation(t *testing.T) {
	cases := []struct {
		name    string
		d1      Float64Data
		d2      Float64Data
		want    float64
		wantErr error
	}{
		{
			name:    "empty input",
			d1:      Float64Data{},
			d2:      Float64Data{},
			want:    math.NaN(),
			wantErr: EmptyInputErr,
		},
		{
			name:    "size mismatch",
			d1:      Float64Data{1, 2, 3},
			d2:      Float64Data{1, 2},
			want:    math.NaN(),
			wantErr: SizeErr,
		},
		{
			name:    "zero std dev returns 0",
			d1:      Float64Data{5, 5, 5},
			d2:      Float64Data{1, 2, 3},
			want:    0,
			wantErr: nil,
		},
		{
			name:    "perfect positive correlation",
			d1:      Float64Data{1, 2, 3},
			d2:      Float64Data{1, 2, 3},
			want:    1,
			wantErr: nil,
		},
		{
			name:    "perfect negative correlation",
			d1:      Float64Data{1, 2, 3},
			d2:      Float64Data{3, 2, 1},
			want:    -1,
			wantErr: nil,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Correlation(tc.d1, tc.d2)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if !correlationApproxEqual(got, tc.want) {
					t.Fatalf("expected %v, got %v", tc.want, got)
				}
			}
		})
	}
}

func TestSpearman(t *testing.T) {
	cases := []struct {
		name    string
		d1      Float64Data
		d2      Float64Data
		want    float64
		wantErr error
	}{
		{
			name:    "inverse perfect with ties",
			d1:      Float64Data{10, 20, 20, 30},
			d2:      Float64Data{30, 20, 20, 10},
			want:    -1,
			wantErr: nil,
		},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := Spearman(tc.d1, tc.d2)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
			if tc.wantErr == nil {
				if !correlationApproxEqual(got, tc.want) {
					t.Fatalf("expected %v, got %v", tc.want, got)
				}
			}
		})
	}
}

func TestPearson(t *testing.T) {
	// Pearson forwards to Correlation; reuse a simple case
	d1 := Float64Data{1, 2, 3}
	d2 := Float64Data{1, 2, 3}
	got, err := Pearson(d1, d2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !correlationApproxEqual(got, 1) {
		t.Fatalf("expected 1, got %v", got)
	}
}

func TestSpearman_EmptyInput(t *testing.T) {
	var empty Float64Data
	_, err := Spearman(empty, Float64Data{1, 2, 3})
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr, got %v", err)
	}
	_, err = Spearman(empty, empty)
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr for both empty, got %v", err)
	}
}

func TestSpearman_SizeMismatch(t *testing.T) {
	d1 := Float64Data{1, 2, 3}
	d2 := Float64Data{4, 5}
	_, err := Spearman(d1, d2)
	if !errors.Is(err, SizeErr) {
		t.Fatalf("expected SizeErr, got %v", err)
	}
}

func TestSpearman_PerfectCorrelation(t *testing.T) {
	d1 := Float64Data{1, 2, 3, 4}
	d2 := Float64Data{10, 20, 30, 40}
	got, err := Spearman(d1, d2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if math.Abs(got-1) > 1e-9 {
		t.Fatalf("expected correlation 1, got %v", got)
	}
}
