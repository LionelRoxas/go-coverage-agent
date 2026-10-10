package stats

import (
	"errors"
	"reflect"
	"testing"
)

func TestQuartileOutliers_EmptyInput(t *testing.T) {
	var input Float64Data
	got, err := QuartileOutliers(input)
	if !errors.Is(err, EmptyInputErr) {
		t.Fatalf("expected EmptyInputErr, got %v", err)
	}
	if len(got.Mild) != 0 || len(got.Extreme) != 0 {
		t.Fatalf("expected empty outliers, got %+v", got)
	}
}

func TestQuartileOutliers_Classification(t *testing.T) {
	input := Float64Data{-20, -10, 1, 2, 3, 4, 5, 6, 7, 8, 9, 20, 30}
	got, err := QuartileOutliers(input)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	wantMild := Float64Data{-10, 20}
	wantExtreme := Float64Data{-20, 30}
	if !reflect.DeepEqual(got.Mild, wantMild) {
		t.Errorf("mild outliers mismatch: got %v, want %v", got.Mild, wantMild)
	}
	if !reflect.DeepEqual(got.Extreme, wantExtreme) {
		t.Errorf("extreme outliers mismatch: got %v, want %v", got.Extreme, wantExtreme)
	}
}
