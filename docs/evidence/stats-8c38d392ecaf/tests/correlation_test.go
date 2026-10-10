package stats

import (
	"errors"
	"math"
	"testing"
)

func correlationFloatClose(t *testing.T, got, want float64) {
	if math.IsNaN(got) && math.IsNaN(want) {
		return
	}
	if math.Abs(got-want) > 1e-9 {
		t.Errorf("float mismatch: got %v want %v", got, want)
	}
}

func TestRankData_Ties(t *testing.T) {
	data := Float64Data{10, 20, 20, 30}
	got := rankData(data)
	want := Float64Data{1, 2.5, 2.5, 4}
	if len(got) != len(want) {
		t.Fatalf("length mismatch: got %d want %d", len(got), len(want))
	}
	for i := range got {
		correlationFloatClose(t, got[i], want[i])
	}
}

func TestRankData_Empty(t *testing.T) {
	var data Float64Data
	got := rankData(data)
	if len(got) != 0 {
		t.Errorf("expected empty slice, got length %d", len(got))
	}
}

func TestAutoCorrelation_Errors(t *testing.T) {
	cases := []struct {
		name    string
		data    Float64Data
		lags    int
		wantErr error
	}{
		{"empty", Float64Data{}, 0, EmptyInputErr},
		{"negative lag", Float64Data{1, 2, 3}, -1, BoundsErr},
		{"lag too large", Float64Data{1, 2, 3}, 3, BoundsErr},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := AutoCorrelation(tc.data, tc.lags)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestAutoCorrelation_ZeroVariance(t *testing.T) {
	data := Float64Data{5, 5, 5}
	got, err := AutoCorrelation(data, 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != 0 {
		t.Errorf("expected 0, got %v", got)
	}
}

func TestAutoCorrelation_Normal(t *testing.T) {
	data := Float64Data{1, 2, 3, 4, 5}
	got, err := AutoCorrelation(data, 1)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	correlationFloatClose(t, got, 0.4)
}

func TestCorrelation_Errors(t *testing.T) {
	cases := []struct {
		name    string
		d1, d2  Float64Data
		wantErr error
	}{
		{"empty first", Float64Data{}, Float64Data{1, 2}, EmptyInputErr},
		{"empty second", Float64Data{1, 2}, Float64Data{}, EmptyInputErr},
		{"size mismatch", Float64Data{1, 2, 3}, Float64Data{1, 2}, SizeErr},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := Correlation(tc.d1, tc.d2)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestCorrelation_ZeroStdDev(t *testing.T) {
	d1 := Float64Data{3, 3, 3}
	d2 := Float64Data{1, 2, 3}
	got, err := Correlation(d1, d2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != 0 {
		t.Errorf("expected 0 when one series has zero stddev, got %v", got)
	}
}

func TestCorrelation_Normal(t *testing.T) {
	d1 := Float64Data{1, 2, 3}
	d2 := Float64Data{2, 4, 6}
	got, err := Correlation(d1, d2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	correlationFloatClose(t, got, 1.0)
}

func TestSpearman_Errors(t *testing.T) {
	cases := []struct {
		name    string
		d1, d2  Float64Data
		wantErr error
	}{
		{"empty", Float64Data{}, Float64Data{1}, EmptyInputErr},
		{"size mismatch", Float64Data{1, 2}, Float64Data{1}, SizeErr},
	}
	for _, tc := range cases {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			_, err := Spearman(tc.d1, tc.d2)
			if !errors.Is(err, tc.wantErr) {
				t.Fatalf("expected error %v, got %v", tc.wantErr, err)
			}
		})
	}
}

func TestSpearman_Ties(t *testing.T) {
	d1 := Float64Data{10, 20, 20, 30}
	d2 := Float64Data{40, 50, 50, 60}
	got, err := Spearman(d1, d2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	correlationFloatClose(t, got, 1.0)
}

func TestPearson_SameAsCorrelation(t *testing.T) {
	d1 := Float64Data{1, 2, 3, 4}
	d2 := Float64Data{2, 4, 6, 8}
	want, err1 := Correlation(d1, d2)
	if err1 != nil {
		t.Fatalf("Correlation error: %v", err1)
	}
	got, err2 := Pearson(d1, d2)
	if err2 != nil {
		t.Fatalf("Pearson error: %v", err2)
	}
	correlationFloatClose(t, got, want)
}
